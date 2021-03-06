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

@login_required
def age_specific_rate_function_redirect(request, id_str, action):
    asrfs = view_utils.id_str_to_objects(id_str, AgeSpecificRateFunction)

    if action == 'edit':
        url = '/admin/dismod3/agespecificratefunction/%d' % asrfs[0].id
    elif action in view_utils.command_list['move']:
        url = reverse('dismod3.views.age_specific_rate_function_show', args=(asrfs[0].id+view_utils.id_delta[action],))
    elif action in view_utils.command_list['sex']:
        url = AgeSpecificRateFunction.objects.filter(disease=asrfs[0].disease, region=asrfs[0].region, rate_type=asrfs[0].rate_type, sex=action)[0].get_absolute_url()
    elif action in view_utils.command_list['format']:
        url = '%s.%s' % (asrfs[0].get_absolute_url(), action)
    else:
        raise Http404
    
    return HttpResponseRedirect(url)


class NotesForm(forms.Form):
    notes = forms.CharField(required=False)
    priors = forms.CharField(required=False, widget=forms.widgets.Textarea())

@login_required
def age_specific_rate_function_clone(request, id):
    asrf = get_object_or_404(AgeSpecificRateFunction, id=id)

    # http customs dictate using POSTs for any interaction which will
    # change the database
    if request.method == 'POST':
        form = NotesForm(request.POST)
        if form.is_valid():
            new_asrf = asrf.clone(**form.cleaned_data)

            # redirect to a page showing the old asrf and the cloned copy
            return HttpResponseRedirect('%s_%d' % (asrf.get_absolute_url(), new_asrf.id))
    else:
        form = NotesForm({'priors': asrf.fit.get('priors', '')})

    return render_to_response('age_specific_rate_function/clone.html', {'rf': asrf, 'form': form})

def url_params_to_dict(string):
    return {}


@login_required
def asrf_posterior_predictive_check_scatter(request, id, format):
    return asrf_posterior_predictive_check(request, id, format, style='scatter')

@login_required
def asrf_posterior_predictive_check_intervals(request, id, format):
    return asrf_posterior_predictive_check(request, id, format, style='intervals')

def same_side_of_xy(x, y):
    x0, x1 = x
    y0, y1 = y
    vals = np.array([x0-y0, x0-y1, x1-y0, x1-y1])
    return (vals >= 0.).all() or (vals <= 0.).all()

@login_required
def asrf_posterior_predictive_check(request, id, format, style):
    """
    generate a posterior predictive check of the model's
    'goodness-of-fit', which is to say a scatterplot of the observed
    rates versus the rates predicted by the model parameters
    """
    rf = get_object_or_404(AgeSpecificRateFunction, id=id)


    params = {'fontsize': 7}
    #params.update(url_params_to_dict(param_str))

    fig= view_utils.clear_plot(width=4,height=3)
    ax = fig.add_subplot(111)
    
    
    if rf.rates.count() == 0 or not rf.fit.has_key('mcmc_mean'):
        pl.figtext(.2, .5, 'Rates or MCMC Fit not found')
    
        return HttpResponse(view_utils.figure_data(format),
                            view_utils.MIMETYPE[format])
    
    observed_rates = np.array([ float(rate.numerator)/float(rate.denominator) for rate in rf.rates.all() ])
    observed_cls = np.transpose([ rate.ci() for rate in rf.rates.all() ])

    predicted_rates = np.array([ probabilistic_utils.predict_rate_from_asrf(rf, rate) for rate in rf.rates.all() ])
    predicted_cls = np.array([ [ probabilistic_utils.predict_rate_from_asrf(rf, rate, 'mcmc_lower_cl') for rate in rf.rates.all() ],
                                [ probabilistic_utils.predict_rate_from_asrf(rf, rate, 'mcmc_upper_cl') for rate in rf.rates.all() ] ])

    max_x = np.max(observed_cls[1,:])
    max_y = np.max(predicted_cls[1,:])
    max_t = max(max_x, max_y, probabilistic_utils.NEARLY_ZERO)

    observed_errs = np.abs(observed_cls - observed_rates)
    predicted_errs = np.abs(predicted_cls - predicted_rates)

    if style == 'scatter':
        pl.plot([probabilistic_utils.NEARLY_ZERO,1.], [probabilistic_utils.NEARLY_ZERO,1.], linestyle='dashed', linewidth=2, color='black', alpha=.75)
        #pl.errorbar(x=observed_rates + np.random.rand(len(observed_rates)) * max_t / 250., xerr=observed_errs,
        #            y=predicted_rates + np.random.rand(len(predicted_rates)) * max_t / 250., yerr=predicted_errs, fmt='bo')
        pl.plot(observed_rates, predicted_rates, '.', alpha=1.)

        from matplotlib.patches import Ellipse
        
        for ii in range(len(observed_rates)):
            e = Ellipse(xy=[np.mean(observed_cls[:,ii]),np.mean(predicted_cls[:,ii])],
                        width=(observed_cls[1,ii] - observed_cls[0,ii]),
                        height=(predicted_cls[1,ii] - predicted_cls[0,ii]),
                        alpha=.05)
            if same_side_of_xy(observed_cls[:,ii], predicted_cls[:,ii]):
                e.set_facecolor((1.,0.,0.))
            ax.add_artist(e)
            
            
        
        pl.axis([-.001, max_t + .001, -.001, max_t + .001])

        tick_list, tick_objs = pl.xticks()
        pl.xticks([0,tick_list[-1]], **params)
        pl.xlabel('Observed Rates', **params)

        tick_list, tick_objs = pl.yticks()
        pl.yticks([0,tick_list[-1]], **params)
        pl.ylabel('Predicted Rates', **params)
    elif style == 'intervals':
        rate_list = rf.rates.all()

        pl.subplot(2,1,1)
        plot_intervals(rf, rate_list, color='green', **params)
        pl.axis([0., 100., 0., max_t])
        pl.xticks([])
        pl.yticks([])
        pl.xlabel('')
        pl.ylabel('')

        for x,r in zip(predicted_rates, rate_list):
            r.numerator = x * r.denominator

        pl.subplot(2,1,2)
        plot_intervals(rf, rate_list, color='red', **params)
        pl.axis([0., 100., 0., max_t])
        pl.xticks([])
        pl.yticks([])
        pl.ylabel('')
        pl.title('')
        
        pl.subplot(2,1,1)
    else:
        raise Exception('ERROR: plot style "%s" unrecognized' % style)
    pl.title('Predictive Check for %s (id=%d)' % (rf, rf.id), **params)
    
    return HttpResponse(view_utils.figure_data(format),
                        view_utils.MIMETYPE[format])

@login_required
def age_specific_rate_function_sparkplot(request, id_str, format='png'):
    asrfs = view_utils.id_str_to_objects(id_str, AgeSpecificRateFunction)

    width = 1
    height = .5
    
    fig = view_utils.clear_plot(width,height)
    pl.subplot(1, 1, 1, frameon=False)
    ax = None
    for ii, rf in enumerate(asrfs):
        plot_truth(rf)
        plot_mcmc_fit(rf)
        #plot_fit(rf, 'mcmc_mean', color='#000000')

        #plot_map_fit(rf)
        #plot_mcmc_fit(rf)
        #plot_prior(rf)
        pl.xticks([])
        pl.yticks([])
        #pl.delaxes()
    pl.subplots_adjust(left=-.1, bottom=0, right=1, top=1.1,
                    wspace=0, hspace=0)

    return HttpResponse(view_utils.figure_data(format),
                        view_utils.MIMETYPE[format])

@login_required
def age_specific_rate_function_show(request, id_str, format='html'):
    asrfs = view_utils.id_str_to_objects(id_str, AgeSpecificRateFunction)

    if format == 'html':
        return render_to_response('age_specific_rate_function/show.html',
                                  view_utils.template_params(asrfs[0], asrfs=asrfs, id_str=id_str, query_str=request.META['QUERY_STRING']))

    # handle json & csv formats
    if format in ['json', 'csv']:
        if format == 'json':
            data_str = json.dumps([[rf.id, rf.fit] for rf in asrfs])
        elif format == 'csv':
            headings = {}
            rows = {}
            data_str = ''

            for rf in asrfs:
                headings[rf] = ['Age (years)', 'MAP Rate (per 1.0)']
                rows[rf] = [[a, p] for a,p in zip(rf.fit['out_age_mesh'], rf.fit['map'])]
                data_str += view_utils.csv_str(headings[rf], rows[rf])
        return HttpResponse(data_str, view_utils.MIMETYPE[format])

    # handle graphics formats
    cnt = asrfs.count()
    cols = 2
    rows = int(np.ceil(float(cnt) / float(cols)))

    subplot_width = 6
    subplot_height = 4
    
    view_utils.clear_plot(width=subplot_width*cols,height=subplot_height*rows)
    for ii, rf in enumerate(asrfs):
        pl.subplot(rows,cols,ii+1)
        if request.GET.get('bars'):
            bars_mcmc_fit(rf)
            #plot_map_fit(rf, alpha=.3)
            plot_truth(rf)
        else:
            plot_intervals(rf, rf.rates.all(), fontsize=12, alpha=.5)
            plot_intervals(rf, rf.rates.filter(params_json__contains='Rural'), fontsize=12, alpha=.5, color='brown')
            #plot_normal_approx(rf)
            plot_map_fit(rf)
            plot_mcmc_fit(rf)
            plot_truth(rf)
            plot_prior(rf)
            pl.text(0,0,rf.fit.get('priors',''), color='black', family='monospace', alpha=.75)
        view_utils.label_plot('%s (id=%d)' % (rf, rf.id), fontsize=10)
        
        max_rate = np.max([.0001] + [r.rate for r in rf.rates.all()] + rf.fit.get('mcmc_upper_cl', []))
        xmin = float(request.GET.get('xmin', default=0.))
        xmax = float(request.GET.get('xmax', default=100.))
        ymin = float(request.GET.get('ymin', default=0.))
        ymax = float(request.GET.get('ymax', default=1.25*max_rate))
        pl.axis([xmin, xmax, ymin, ymax])

        if ii % cols != 0:
            pl.ylabel('')
        #pl.yticks([])
        if (ii + cols) < cnt:
            pl.xlabel('')
        #pl.xticks([])
    
    
    return HttpResponse(view_utils.figure_data(format),
                        view_utils.MIMETYPE[format])

@login_required
def age_specific_rate_function_compare(request, id_str, format='html'):
    """
    display information for comparing multiple age specific rate functions
    
    id_str is a comma separate list of asrf ids, and format can be html
    or a graphics format that is recognized by matplotlib
    """
    asrfs = view_utils.id_str_to_objects(id_str, AgeSpecificRateFunction)
    if format == 'html':
        return render_to_response('age_specific_rate_function/compare.html', {'id_str': id_str, 'asrfs': asrfs})

    size = request.GET.get('size', default='normal')
    style = request.GET.get('style', default='overlay')

    if size == 'small':
        width = 3
        height = 2
    elif size == 'full_page':
        width = 11
        height = 8.5
    else:
        width = 6
        height = 4

    max_rate = .0001

    view_utils.clear_plot(width=width,height=height)
    try:
        if style == 'overlay':
            for ii, rf in enumerate(asrfs):
                plot_fit(rf, 'map', alpha=.75, linewidth=5, label='asrf %d'%rf.id)
                max_rate = np.max([max_rate] + rf.fit['map'])
            pl.axis([0, 100, 0, 1.25*max_rate])

        elif style == 'scatter':
            x, y = [ [ asrfs[ii].fit[fit_type] for fit_type in ['mcmc_mean', 'mcmc_lower_cl', 'mcmc_upper_cl'] ] for ii in [0,1] ]

            max_x = np.max(x[2])
            max_y = np.max(y[2])
            max_t = max(max_x, max_y, .00001)

            xerr = np.abs(np.array(x[1:]) - np.array(x[0]))
            yerr = np.abs(np.array(y[1:]) - np.array(y[0]))

            pl.plot([probabilistic_utils.NEARLY_ZERO,1.], [probabilistic_utils.NEARLY_ZERO,1.], linestyle='dashed', linewidth=2, color='black', alpha=.75)
            pl.errorbar(x=x[0], xerr=xerr, y=y[0], yerr=yerr, fmt='bo')
            pl.axis([0,max_t,0,max_t])

        elif style == 'stack':
            n = asrfs.count()
            max_t = probabilistic_utils.NEARLY_ZERO
            for ii in range(n):
                x = asrfs[ii].fit['mcmc_mean']
                max_t = max(np.max(x), max_t)

                pl.subplot(n, 1, ii+1, frameon=False)
                pl.plot(x, linewidth=3)
                if size != 'small':
                    pl.title(asrfs[ii])
                pl.axis([0, 100, 0, max_t*1.1])
                pl.xticks([])
                pl.yticks([])
            pl.subplots_adjust(left=0, right=1)

        elif style == 'parallel':
            for xx in zip(*[ rf.fit['mcmc_mean'] for rf in asrfs ]):
                pl.plot(xx, linewidth=2, color='blue', alpha=.5)
            xmin, xmax, ymin, ymax = pl.axis()
            pl.vlines(range(len(asrfs)), ymin, ymax, color='black', linestyles='dashed',
                      alpha=.5, linewidth=2)
            pl.xticks(range(len(asrfs)), [ 'asrf %d' % rf.id for rf in asrfs ])
    except KeyError:
        pass
        #pl.figtext(0.4,0.2, 'No MCMC Fit Found')

    if size == 'small':
        pl.xticks([])
        pl.yticks([])
    else:
        if style != 'stack' and style != 'parallel':
            pl.legend()
            view_utils.label_plot('Comparison of Age-Specific Rate Functions')

    return HttpResponse(view_utils.figure_data(format),
                        view_utils.MIMETYPE[format])
        
class ASRFCreationForm(forms.Form):
    disease = forms.ModelChoiceField(Disease.objects.all())
    region = forms.ModelChoiceField(Region.objects.all(), required=False)
    rate_type = forms.ChoiceField(fields.ALL_OPTION + fields.RATE_TYPE_CHOICES, required=False)
    sex = forms.ChoiceField(fields.ALL_OPTION + fields.SEX_CHOICES)
    notes = forms.CharField(required=False, widget=forms.widgets.Textarea())

@login_required
def age_specific_rate_function_index(request):
    if request.method == 'POST': # If the form has been submitted...
        form = ASRFCreationForm(request.POST) # A form bound to the POST data
        if form.is_valid(): # All validation rules pass
            asrfs = age_specific_rate_function.create_multiple(**form.cleaned_data)
            return HttpResponseRedirect('/age_specific_rate_function/%s' % view_utils.objects_to_id_str(asrfs)) # Redirect after POST
    else:
        form = ASRFCreationForm()

    asrfs = AgeSpecificRateFunction.objects.all().order_by('-id')
    paginated_models = view_utils.paginated_models(request, asrfs)
                                                   

    return render_to_response('age_specific_rate_function/index.html', {'form': form, 'paginated_models': paginated_models})

def plot_intervals(rf, rate_list, alpha=.75, color=(.0,.5,.0), text_color=(.0,.3,.0), fontsize=12):
    """
    use matplotlib plotting functions to render transparent
    rectangles on the current figure representing each
    piece of RateData that will be used in fitting this
    age-specific rate function
    """
    for r in rate_list:
        if r.age_end == fields.MISSING:
            r.age_end = probabilistic_utils.MAX_AGE
        
        rate_val = float(r.numerator)/float(r.denominator)
        x_jitter = 0.*np.random.rand()
        y_jitter = 0.
        pl.plot(.5*np.array([(r.age_start+r.age_end+1)]*2)+x_jitter,
                r.ci(),
                color=color, alpha=alpha, linewidth=1)
        pl.plot(np.array([r.age_start, r.age_end+1.]),
                np.array([rate_val,rate_val]),
                color=color, alpha=alpha, linewidth=5,
                )
        # pl.text(r.age_end+x_jitter, rate_val+y_jitter,
        #         "n=%d" % r.rate_denominator,
        #         color=text_color, alpha=alpha, fontsize=8)
    view_utils.label_plot('%s (id=%d)' % (rf, rf.id), fontsize=fontsize)
    
def plot_fit(rf, fit_name, **params):
    try:
        rate = rf.fit[fit_name]
        pl.plot(rf.fit['out_age_mesh'], rate, **params)
    except (AssertionError, KeyError, ValueError):
        pass
        #pl.figtext(0.4,0.2, 'No %s data Found' % fit_name)

def plot_normal_approx(rf):
    plot_fit(rf, 'normal_approx', color='blue', alpha=.5)

def plot_truth(rf):
    if rf.fit.has_key('truth'):
        x = np.array(rf.fit['truth'])
        pl.plot(x[:,0], x[:,1], ':', color='green', alpha=.95, linewidth=2)

def plot_map_fit(rf, **params):
    default_params = {'color': 'blue',
                      'linestyle': 'dashed',
                      'linewidth': 2,
                      'alpha': .9,
                      }
    plot_fit(rf, 'map', **default_params)

def plot_mcmc_fit(rf, detailed_legend=False, color=(.2,.2,.2)):
    try:
        x = np.concatenate((rf.fit['out_age_mesh'], rf.fit['out_age_mesh'][::-1]))
        y = np.concatenate((rf.fit['mcmc_lower_cl'], rf.fit['mcmc_upper_cl'][::-1]))

        pl.fill(x, y, facecolor='.2', edgecolor=color, alpha=.5)

        mcmc_avg = rf.fit['mcmc_mean']

        if detailed_legend:
            label = str(rf.region)
            color = np.random.rand(3)
        else:
            label = 'MCMC Fit'
            color = color

        pl.plot(rf.fit['out_age_mesh'], mcmc_avg, color=color, linewidth=3, alpha=.75, label=label)
    except (KeyError, ValueError):
        pass
        #pl.figtext(0.4,0.4, 'No MCMC Fit Found')

def weighted_average(age_mesh, rate, age_bins):
    num_bins = len(age_bins) - 1
    bin_sum = np.zeros(num_bins)
    bin_cnt = np.zeros(num_bins)
    bin_for = [0]*len(age_mesh)

    age_bins = copy.copy(age_bins)
    age_bins.append(np.inf)
    ii=-1
    for a, r in zip(age_mesh, rate):
        if a >= age_bins[ii+1]:
            ii += 1
        bin_for[a] = ii
        if ii >= 0 and ii < num_bins:
            bin_sum[ii] += r
            bin_cnt[ii] += 1
        
    return bin_sum / bin_cnt

def bars_mcmc_fit(rf, ages = [0,5,10,15,20,25,30,35,40,45,55,65,75,85,100]):
    """
    make a barplot of mcmc fit data
    """
    try:
        # plot bars
        params = {}
        params['left'] = ages[:-1]
        params['width'] = np.diff(ages)

        params['height'] = weighted_average(rf.fit['out_age_mesh'], rf.fit['mcmc_median'], ages)
        print 'height = ', params['height']
        
        color = '#5cbe5c' # light green
        color = '#be5c5c' # light red
        params['color'] = color
        params['edgecolor'] = color
        pl.bar(**params)

        # plot error ticks
        params = {}
        params['x'] = 0.5 * (np.array(ages[:-1]) + np.array(ages[1:]))
        params['y'] = weighted_average(rf.fit['out_age_mesh'], rf.fit['mcmc_median'], ages)
        #print 'y = ', params['y']

        err_below = params['y'] - weighted_average(rf.fit['out_age_mesh'], rf.fit['mcmc_lower_cl'], ages)
        err_above = weighted_average(rf.fit['out_age_mesh'], rf.fit['mcmc_upper_cl'], ages) - params['y']
        #print err_below
        #print err_above
        params['yerr'] = [err_below, err_above]

        #params['fmt'] = 'o'
        params['fmt'] = None
               
        color = '#0c860c' # darker green
        color = '#860c0c' # darker red
        params['ecolor'] = color
        params['color'] = color 
        pl.errorbar(**params)
        
    except (KeyError):
        pass
        #pl.figtext(0.4,0.4, 'No MCMC Fit Found')
    

def plot_prior(rf):
    # use prior to set rate near zero as requested
    for prior_str in rf.fit.get('priors', '').split('\n'):
        prior = prior_str.split()
        if len(prior) > 0 and prior[0] == 'zero':
            age_start = int(prior[1])
            age_end = int(prior[2])

            pl.plot([age_start, age_end], [0, 0], color='red', linewidth=15, alpha=.75)
