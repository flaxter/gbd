from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import *
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django import forms

import pymc.gp as gp
import numpy as np
import pylab as pl

from dismod3.models import fields
from dismod3.views import view_utils

from models import *

def max_min_str(num_list):
    a = min(num_list)
    b = max(num_list)
    if a == b:
        return '%d' % a
    else:
        return '%d-%d' % (a,b)

def clean(str):
    return str.strip().lower().replace(' ', '_')

import csv
def unicode_csv_reader(unicode_csv_data, dialect=csv.excel, **kwargs):
    # csv.py doesn't do Unicode; encode temporarily as UTF-8:
    csv_reader = csv.reader(utf_8_encoder(unicode_csv_data),
                            dialect=dialect, **kwargs)
    for row in csv_reader:
        # decode UTF-8 back to Unicode, cell by cell:
        yield [unicode(cell, 'utf-8') for cell in row]

def utf_8_encoder(unicode_csv_data):
    for line in unicode_csv_data:
        yield line.encode('utf-8')
                
class NewDataForm(forms.Form):
    required_data_fields = ['GBD Cause', 'Region', 'Parameter', 'Sex', 'Country',
                            'Age Start', 'Age End', 'Year Start', 'Year End',
                            'Parameter Value', 'Standard Error', 'Units', ]

    tab_separated_values = forms.CharField(required=True, widget=forms.widgets.Textarea(), help_text='See "data input spec" for details')

    def clean_tab_separated_values(self):
        tab_separated_values = self.cleaned_data['tab_separated_values']
        from StringIO import StringIO
        #import pdb; pdb.set_trace()
        lines = unicode_csv_reader(StringIO(tab_separated_values), dialect='excel-tab')

        col_names = [clean(col) for col in lines.next()]
        #import pdb; pdb.set_trace()

        # check that required fields appear
        for field in NewDataForm.required_data_fields:
            if not clean(field) in col_names:
                raise forms.ValidationError('Column "%s" is missing' % field)

        data_list = []
        for ii, cells in enumerate(lines):
            # skip blank lines
            if sum([cell == '' for cell in cells]) == 0:
                continue
            
            # ensure that something appears for each column
            if len(cells) != len(col_names):
                raise forms.ValidationError('Error loading row %d:  found %d fields (expected %d)' % (ii+2, len(cells), len(col_names)))

            # make an associative array from the row data
            data = {}
            for key, val in zip(col_names, cells):
                data[clean(key)] = val.strip()
                data['_row'] = ii+2

            data_list.append(data)

        # ensure that certain cells are the right format
        #import pdb; pdb.set_trace()
        error_str = 'Row %d:  could not understand entry for %s'
        for r in data_list:
            try:
                r['parameter'] = fields.standardize_data_type[r['parameter']]
            except KeyError:
                raise forms.ValidationError(error_str % (r['_row'], 'Parameter'))
            try:
                r['sex'] = fields.standardize_sex[r['sex']]
            except KeyError:
                raise forms.ValidationError(error_str % (r['_row'], 'Sex'))
            try:
                r['age_start'] = int(r['age_start'])
                # some people think it is a good idea to use 99 as a missing value
                if r['age_start'] == 99:
                    r['age_start'] = 0
                    
                r['age_end'] = int(r['age_end'] or fields.MISSING)
                r['year_start'] = int(r['year_start'])
                r['year_end'] = int(r['year_end'])
            except (ValueError, KeyError):
                raise forms.ValidationError(error_str % (r['_row'], 'at least one of Age Start, Age End, Year Start, Year End'))
            try:
                r['parameter_value'] = float(r['parameter_value'])
            except ValueError:
                r['parameter_value'] = fields.MISSING

            try:
                r['standard_error'] = float(r['standard_error'])
            except ValueError:
                r['standard_error'] = fields.MISSING
                # raise forms.ValidationError(error_str % (r['_row'], 'Standard Error'))
            except KeyError:
                raise forms.ValidationError(error_str % (r['_row'], 'Standard Error'))
            # TODO: catch ValueError and KeyError, and raise informative error instead, forms.ValidationError('useful msg here')
            # and write tests for this, too
        return data_list


@login_required
def data_new(request):
    if request.method == 'GET':     # no form data is associated with page, yet
        form = NewDataForm()
    elif request.method == 'POST':  # If the form has been submitted...
        form = NewDataForm(request.POST) # A form bound to the POST data

        if form.is_valid(): # All validation rules pass, create new data based on the form contents
            data_table = form.cleaned_data['tab_separated_values']

            # make rates from rate_list
            data_list = []
            for d in data_table:
                # add a rate, save it on a list
                args = {}
                args['condition'] = d['gbd_cause']
                args['gbd_region'] = d['region']
                args['region'] = d['country']
                args['data_type'] = d['parameter']
                args['sex'] = d['sex']
                args['age_start'] = d['age_start']
                args['age_end'] = d['age_end']
                args['year_start'] = d['year_start']
                args['year_end'] = d['year_end']

                args['value'] = d['parameter_value']
                args['standard_error'] = d['standard_error']

                # copy mapped data back into d, so that it appears in
                # params
                d.update(args)
                args['defaults'] = {'params_json': json.dumps(d)}

                d, is_new = Data.objects.get_or_create(**args)
                d.calculate_age_weights()
                data_list.append(d)
                
            # collect this data together into a new model
            args = {}
            args['condition'] = ', '.join(set([d.condition for d in data_list]))
            args['sex'] = ', '.join(set([d.sex for d in data_list]))
            args['region'] = '; '.join(set([d.region for d in data_list]))
            args['year'] = max_min_str([d.year_start for d in data_list] + [d.year_end for d in data_list])

            #import pdb; pdb.set_trace()
            dm = DiseaseModel.objects.create(**args)
            for d in data_list:
                dm.data.add(d)
            dm.cache_params()
            dm.save()
            
            return HttpResponseRedirect(dm.get_absolute_url()) # Redirect after POST

    return render_to_response('data_new.html', {'form': form})


@login_required
def data_show(request, id):
    data = get_object_or_404(Data, pk=id)
    data.view_list = [[_('Condition'), data.condition],
                      [_('Data Type'), data.data_type],
                      [_('Sex'), data.get_sex_display()],
                      [_('GBD Region'), data.gbd_region],
                      [_('Region'), data.region],
                      [_('Age'), data.age_str()],
                      [_('Year'), data.year_str()],
                      [_('Value'), data.value_str()],
                      ]
    return render_to_response('data_show.html', view_utils.template_params(data))


@login_required
def disease_model_show(request, id, format='html'):
    dm = get_object_or_404(DiseaseModel, id=id)

    if format == 'html':
        return render_to_response('disease_model_show.html', view_utils.template_params(dm))
    elif format == 'json':
        return HttpResponse(dm.to_json(), view_utils.MIMETYPE[format])
    elif format in ['png', 'svg', 'eps', 'pdf']:
        from gbd import dismod3
        dismod3.plot_disease_model(dm.to_json())
        return HttpResponse(view_utils.figure_data(format),
                            view_utils.MIMETYPE[format])
    else:
        raise Http404


class NewDiseaseModelForm(forms.Form):
    model_json = forms.CharField(required=True, widget=forms.widgets.Textarea(),
                                 help_text='See source for details')
    def clean_model_json(self):
        model_json = self.cleaned_data['model_json']
        try:
            model_dict = json.loads(model_json)
        except ValueError:
            raise forms.ValidationError('JSON object could not be decoded')
        if not model_dict.get('params'):
            raise forms.ValidationError('missing params')
        if not model_dict['params'].get('condition'):
            raise forms.ValidationError('missing params.condition')
        if not model_dict['params'].get('sex'):
            raise forms.ValidationError('missing params.sex')
        if not model_dict['params'].get('region'):
            raise forms.ValidationError('missing params.region')
        if not model_dict['params'].get('year'):
            raise forms.ValidationError('missing params.year')
        return model_dict

@login_required
def disease_model_new(request):
    if request.method == 'GET':     # no form data is associated with page, yet
        form = NewDiseaseModelForm()
    elif request.method == 'POST':  # If the form has been submitted...
        form = NewDiseaseModelForm(request.POST) # A form bound to the POST data

        if form.is_valid():
            # All validation rules pass, so create new
            dm = create_disease_model(form.cleaned_data['model_json'])
            return HttpResponseRedirect(dm.get_absolute_url()) # Redirect after POST

    return render_to_response('disease_model_new.html', {'form': form})
