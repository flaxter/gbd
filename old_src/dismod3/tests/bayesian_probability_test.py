# Testing the Bayesian probability code is complicated because (1) the
# model is still being developed and (2) the output is random

# But you've gotta try...

# Instead of using fixtures, I'm going to try creating everything
# here.  I think that this will be clearer, but if it becomes very
# laborious, I should revisit this decision
import numpy as np
import pymc as mc

def create_test_rates(rate_function_str='(age/100.0)**2', rate_type='prevalence data',
                      age_list=None, num_subjects=1000):
    import dismod3.models as models

    if not age_list:
        #age_list = range(0,101,10)
        age_list = np.random.random_integers(0,90,20)

    params = {}
    params['disease'], flag = models.Disease.objects.get_or_create(name='Test Disease')
    params['region'], flag = models.Region.objects.get_or_create(name='World')
    params['rate_type'] = rate_type
    params['sex'] = 'total'
    params['country'] = 'Canada'
    params['epoch_start'] = 2000
    params['epoch_end'] = 2000
    

    rate_list = []

    # TODO: make this safe and robust
    if isinstance(rate_function_str, str):
        rate_function = eval('lambda age: %s'%rate_function_str)
    else:
        from scipy.interpolate import interp1d

        rf_vals = np.array(rate_function_str) # it is actually an Nx2 array
        rate_function = interp1d(rf_vals[:,0], rf_vals[:,1], kind='cubic')


    rate_vec = np.array([rate_function(a) for a in range(101)])
    
    for a in age_list:
        #params['age_start'] = a-5
        params['age_start'] = a

        #params['age_end'] = params['age_start']
        #params['age_end'] = a+5
        params['age_end'] = np.random.random_integers(a, 100)

        params['denominator'] = num_subjects
        params['numerator'] = 0
        
        new_rate = models.Rate(**params)
        new_rate.params['Notes'] = 'Simulated data, created using function %s' % rate_function_str
        new_rate.params['Urbanicity'] = (np.random.randn() > 0) and 'Urban' or 'Rural'
        
        new_rate.save()

        p = probabilistic_utils.rate_for_range(rate_vec, new_rate.age_start, new_rate.age_end, new_rate.population())

        # adjust p to make data heterogeneous according to 'Urbanicity' covariate
        if new_rate.params['Urbanicity'] == 'Urban':
            p *= 1.5

        #multiplicative_noise = 1.
        #multiplicative_noise = 1 + 0.1*np.random.randn()
        #new_rate.numerator = multiplicative_noise * \
        #                     new_rate.denominator * probabilistic_utils.rate_for_range(rate_vec, new_rate.age_start, new_rate.age_end, new_rate.population())
        new_rate.numerator = mc.rbinomial(new_rate.denominator, p)

        new_rate.save()

        
        rate_list.append(new_rate)

    return rate_list, rate_function

def create_test_asrf(rate_function_str='(age/100.0)**2',
                     rate_type='prevalence data',
                     age_list=None, num_subjects=1000,
                     priors=''):
    """
    create a new asrf for testing purposes, by evaluating the
    rate_function_str at places given on the age_list (or
    range(0,100,5) if no age_list is specified).

    return the age specific rate function object, for additional
    processing, like setting priors with add_priors(rf, ...)
    """
    import dismod3.models as models

    print 'creating %s with rate(age) = %s (priors: %s)' % (rate_type, rate_function_str, priors)

    params = {}
    params['disease'], flag = models.Disease.objects.get_or_create(name='Test Disease')
    params['region'], flag = models.Region.objects.get_or_create(name='World')
    params['rate_type'] = rate_type
    params['sex'] = 'total'
    params['notes'] = 'Simulated rate function, created using %s, with age_list %s' % (rate_function_str, str(age_list))

    rf = models.AgeSpecificRateFunction(**params)
    rf.save()
    rf.rates, rate_function = create_test_rates(rate_function_str, rate_type, age_list, num_subjects)
    rf.fit['truth'] = [[ii, rate_function(ii)] for ii in range(100)]
    if priors:
        rf.fit['priors'] = priors
    else:
        add_priors(rf, smooth_tau=100.0, zero_until=-1, zero_after=-1)
    rf.save()


    return rf

def add_priors(rf, smooth_tau=.1, zero_until=5, zero_after=95):
    """
    add priors to age specific rate function (which can be an object or an id)

    omit zero prior if zero_xxx = -1
    """
    import dismod3.models as models

    if not isinstance(rf, models.AgeSpecificRateFunction):
        rf = models.AgeSpecificRateFunction.objects.get(id=rf)
    rf.fit['priors'] = 'smooth %f\n' % smooth_tau
    if zero_until != -1:
        rf.fit['priors'] += 'zero 0 %d\n' % zero_until
    if zero_after != -1:
        rf.fit['priors'] += 'zero %d 100\n' % zero_after

    rf.save()

import numpy as np

from base_test import DisModTestCase
from dismod3.models import *

class BayesianProbabilityTestCase(DisModTestCase):
    def test_interpolation(self):
        c_vals = probabilistic_utils.const_func([1,2,3], 17.0)
        assert (c_vals == [ 17., 17., 17.]).all()

        M,C = probabilistic_utils.uninformative_prior_gp()
        assert (M([0,10,100]) == [-10., -10., -10.]).all()
        
        i_vals = probabilistic_utils.interpolate([0, 25, 50, 100], [0, 25, 50, 100], [0, 100])
        assert (i_vals == [ 0., 100.]).all()
