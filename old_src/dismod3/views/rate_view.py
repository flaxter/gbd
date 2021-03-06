from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import *
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django import forms

import pymc.gp as gp
import numpy as np
import pylab as pl

from dismod3.models import *
import view_utils

def clean(str):
    return str.lower().replace(' ', '')

class RateCreationForm(forms.Form):
    tab_separated_values = forms.CharField(required=True, widget=forms.widgets.Textarea(), help_text='See "rate input spec.doc" for details')

    def clean_tab_separated_values(self):
        # TODO: make a special form derived from CharField that does this split with the csv package
        tab_separated_values = self.cleaned_data['tab_separated_values']
        lines = tab_separated_values.split('\n')

        col_names = [clean(col) for col in lines.pop(0).split('\t')]

        # check that required fields appear
        for field in ['GBD Cause', 'Region', 'Parameter', 'Sex', 'Country',
                      'Age Start', 'Age End', 'Estimate Year Start', 'Estimate Year End',
                      'Parameter Value', 'Lower Value', 'Upper Value', 'Units', 'Type of Bounds', ]:
            if not clean(field) in col_names:
                raise forms.ValidationError('Column "%s" is missing' % field)

        rate_list = []
        for ii, line in enumerate(lines):
            # skip blank lines
            if line == '':
                continue

            data = line.split('\t')
            
            # ensure that something appears for each column
            if len(data) != len(col_names):
                raise forms.ValidationError('Error loading row %d:  missing fields detected' % (ii+2))

            # make an associative array from the row data
            rate = {}
            for key, val in zip(col_names, data):
                rate[clean(key)] = val.strip()

            rate_list.append(rate)

        # ensure that certain cells are the right format
        #import pdb; pdb.set_trace()
        for r in rate_list:
            r['parameter'] = fields.standardize_rate_type[r['parameter']]
            r['sex'] = fields.standardize_sex[r['sex']]
            r['agestart'] = int(r['agestart'])
            r['ageend'] = int(r['ageend'] or fields.MISSING)
            r['estimateyearstart'] = int(r['estimateyearstart'])
            r['estimateyearend'] = int(r['estimateyearend'])
            r['parametervalue'] = float(r['parametervalue'])
            r['lowervalue'] = float(r['lowervalue'] or fields.MISSING)
            r['uppervalue'] = float(r['uppervalue'] or fields.MISSING)
            r['units'] = float((re.findall('([\d\.]+)', r['units']) or [fields.MISSING])[0])
            r['typeofbounds'] = float((re.findall('([\d\.]+)', r['typeofbounds']) or [fields.MISSING])[0])
            # TODO: catch ValueError and KeyError, and raise informative error instead, forms.ValidationError('useful msg here')
            # and write tests for this, too
        return rate_list

@login_required
def rate_index(request):
    if request.method == 'POST': # If the form has been submitted...
        form = RateCreationForm(request.POST) # A form bound to the POST data
        if form.is_valid(): # All validation rules pass
            rate_list = form.cleaned_data['tab_separated_values']

            # make rates from rate_list
            rates = []
            for r in rate_list:
                # add a rate, save it on a list
                args = {}
                args['disease'], c = Disease.objects.get_or_create(name=r['gbdcause'])  # c is an unused flag for whether or not this object was just _c_reated
                args['region'], c = Region.objects.get_or_create(name=r['region'])
                args['rate_type'] = r['parameter']
                args['sex'] = r['sex']
                args['country'] = r['country']
                args['age_end'] = r['ageend']
                args['age_start'] = r['agestart']
                args['epoch_start'] = r['estimateyearstart']
                args['epoch_end'] = r['estimateyearend']

                # TODO: deal with the standard error correctly
                if r['units'] == fields.MISSING:
                    r['units'] = 1.0
                args['numerator'] = r['parametervalue'] / r['units'] * 5000
                args['denominator'] = 5000
                
                args['params_json'] = json.dumps(r)

                r = Rate(**args)
                r.save()
                rates.append(r)
                
            # make asrfs to collect all rates by rate_type
            asrfs = []
            for rate_type in fields.all_options(fields.RATE_TYPE_CHOICES):
                rates_by_type = [r for r in rates if r.rate_type == rate_type]
                if len(rates_by_type) > 0:
                    r = rates_by_type[0]
                    rf = AgeSpecificRateFunction(disease=r.disease, region=r.region, rate_type=r.rate_type, sex=r.sex)
                    rf.save()
                    rf.rates = rates_by_type
                    rf.save()
                    asrfs.append(rf)

            # redirect to view all asrfs
            return HttpResponseRedirect('/age_specific_rate_function/%s' % view_utils.objects_to_id_str(asrfs)) # Redirect after POST
    else:
        form = RateCreationForm()

    return render_to_response('rate/index.html', {'form': form})


@login_required
def rate_show(request, id):
    rate = get_object_or_404(Rate, pk=id)
    rate.view_list = [[_('Disease'), rate.disease],
                      [_('Rate Type'), rate.get_rate_type_display()],
                      [_('Sex'), rate.get_sex_display()],
                      [_('Region'), rate.region],
                      [_('Country'), rate.country],
                      [_('Age Range'), '%d-%d' % (rate.age_start, rate.age_end)],
                      [_('Epoch'), '%d-%d' % (rate.epoch_start, rate.epoch_end)],
                      [_('Rate'), '%d/%d = %0.5f' % (rate.numerator, rate.denominator, rate.rate)],
                      ]
    return render_to_response('rate/show.html', view_utils.template_params(rate))

@login_required
def rate_redirect(request, id, action):
    rate = get_object_or_404(Rate, pk=id)
    if action == 'edit':
        url = '/admin/dismod3/rate/%d' % rate.id
    elif action in view_utils.command_list['move']:
        url = reverse('dismod3.views.rate_show', args=(rate.id+view_utils.id_delta[action],))
    elif action in view_utils.command_list['sex']:
        url = '/rate/plot/disease_%s-rate_%s-region_%s-sex_%s.png' % (rate.disease.id, rate.rate_type[:4], rate.region.id, action)
    elif action in view_utils.command_list['format']:
        url = '/rate/plot/disease_%s-rate_%s-region_%s-sex_%s.%s' % (rate.disease.id, rate.rate_type[:4], rate.region.id, rate.sex, action)
    else:
        raise Http404
    
    return HttpResponseRedirect(url)

@login_required
def rate_plot(request, path, format='png'):
    """
    use matplotlib plotting functions to render transparent
    rectangles on the current figure representing each
    piece of RateData that will be used in fitting this
    age-specific rate function

    path is the format param_value-param2_value2-..., where
    each param is from the list
      [disease, rate, region, sex, limit]
    values for region and disease are the id of the object,
    limit is an int upper-bound on number of rates to plot,
    and all the other options will do partial name matching
    """
    filter_params = {'limit': '100'}
    for p in path.split('-'):
        param, value = p.split('_')
        if param == 'disease':
            filter_params['disease__id'] = int(value)
        elif param == 'rate':
            filter_params['rate_type__contains'] = value
        elif param == 'region':
            filter_params['region__id'] = int(value)
        elif param == 'sex':
            filter_params['sex'] = value
        elif param == 'limit':
            filter_params['limit'] = value
        else:
            raise KeyError
            
    limit = int(filter_params.pop('limit'))
    rates = Rate.objects.filter(**filter_params)

    view_utils.clear_plot()
    for r in rates[:limit]:
        rate_val = float(r.numerator)/float(r.denominator)
        x_jitter = np.random.rand()
        y_jitter = 0.
        if r.sex == 'male':
            color = (0.,0.,.8)
        elif r.sex == 'female':
            color = (.8,0.,0.)
        else:
            color = (0.,.8,0.)
            
        text_color = 'black'
        alpha=.65
        pl.plot(np.array([r.age_start, r.age_end+1.])+x_jitter, 
                np.array([rate_val,rate_val])+y_jitter,
                color=color, alpha=alpha, linewidth=5,)
        pl.text(r.age_end+x_jitter, rate_val+y_jitter,
                "n=%d" % r.denominator,
                color=text_color, alpha=alpha, fontsize=6)
    view_utils.label_plot(path.replace('-', ', ').replace('_', ': '))

    
    return HttpResponse(view_utils.figure_data(format),
                        view_utils.MIMETYPE[format])

