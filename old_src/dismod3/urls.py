from django.conf.urls.defaults import *

urlpatterns = patterns('dismod3.views',
    (r'population/(\d+)$', 'population_show'),
    (r'population/(\d+)\.(\w+)$', 'population_plot'),
    (r'population/(\d+)/(\w+)$', 'population_redirect'),

    (r'rate/$', 'rate_index'),
    (r'rate/(\d+)$', 'rate_show'),
    (r'rate/(\d+)/(\w+)$', 'rate_redirect'),
    (r'rate/plot/([\w-]+)\.(\w+)$', 'rate_plot'),

    (r'age_specific_rate_function/$', 'age_specific_rate_function_index'),
    (r'age_specific_rate_function/compare/(\w+)_compare\.(\w+)', 'age_specific_rate_function_compare'),
    (r'age_specific_rate_function/compare/(\w+)$', 'age_specific_rate_function_compare'),
    (r'age_specific_rate_function/asrf_(\w+)_sparkplot.(\w+)$', 'age_specific_rate_function_sparkplot'),
    (r'age_specific_rate_function/(\w+)\.(\w+)', 'age_specific_rate_function_show'),
    (r'age_specific_rate_function/(\w+)$', 'age_specific_rate_function_show'),
    (r'age_specific_rate_function/(\d+)/clone$', 'age_specific_rate_function_clone'),
    (r'age_specific_rate_function/(\w+)/(\w+)$', 'age_specific_rate_function_redirect'),
    (r'age_specific_rate_function/posterior_predictive_check/(\w+)_ppc_intervals\.(\w+)$', 'asrf_posterior_predictive_check_intervals'),
    (r'age_specific_rate_function/posterior_predictive_check/(\w+)_ppc_scatter\.(\w+)$', 'asrf_posterior_predictive_check_scatter'),

    (r'disease_model/dm_(\d+)_sparkplot.(\w+)$', 'disease_model_sparkplot'),
    (r'disease_model/(\d+)$', 'disease_model_show'),
    (r'disease_model/$', 'disease_model_index'),

#    (r'dm/(\w+)', 'disease_model_show'),
#    (r'rf/(\w+)', 'age_specific_rate_function_show'),

#    (r'$', 'index'),
)
