import numpy as np
import pymc as mc
import random

import dismod3
from dismod3.utils import trim, interpolate, rate_for_range, indices_for_range, generate_prior_potentials, clean, type_region_year_sex_from_key
from dismod3.settings import NEARLY_ZERO, MISSING

def fit_emp_prior(dm, param_type, prior_str=None):
    """ Generate an empirical prior distribution for a single disease parameter

    Parameters
    ----------
    dm : dismod3.DiseaseModel
      The object containing all the data, (hyper)-priors, and additional
      information (like input and output age-mesh).

    param_type : str, one of 'incidence', 'prevalence', 'remission', 'excess-mortality'
      The disease parameter to work with

    prior_str : str, optional
      The (hyper)-prior for this disease parameter; see
      utils.generate_prior_potentials for format

    Notes
    -----
    The results of this fit are stored in the disease model's params
    hash for use when fitting multiple paramter types together

    Example
    -------
    >>> import dismod3
    >>> import dismod3.beta_binomial_model as model
    >>> dm = dismod3.get_disease_model(1)
    >>> model.fit_emp_prior(dm, 'incidence', 'zero 0 4, smooth 25')
    >>> assert dm.params.has_key('emp_prior')
    >>> assert dm.params['emp_prior'].has_key('incidence')
    >>> dismod3.post_disease_model(dm)
    """
    if prior_str:
        dm.set_priors(param_type, prior_str)

    # remove the old PyMC model, if it exists
    if hasattr(dm, 'vars'):
        delattr(dm, 'vars')
    if hasattr(dm, 'map'):
        delattr(dm, 'map')
    dm.set_empirical_prior(param_type, {})
    
    # fit the model
    fit(dm, method='map', param_type=param_type)

    # save the results in the param_hash
    mu = dm.vars['rate_stoch'].value
    se = mu * (1-mu) * np.sqrt(dm.vars['dispersion'].value)
    dm.set_empirical_prior(param_type, {'mu': list(mu),
                                        'se': list(se),
                                        'dispersion': float(dm.vars['dispersion'].value)})
    
    for r in dismod3.gbd_regions:
        for y in dismod3.gbd_years:
            for s in dismod3.gbd_sexes:
                key = dismod3.gbd_key_for(param_type, r, y, s)
                dm.set_map(key, mu)
                dm.set_mcmc('lower_ui', key, mu - 1.96*se)
                dm.set_mcmc('upper_ui', key, mu + 19.6*se)
                #dm.set_mcmc('mean', key, mu)

                #dm.set_mcmc('dispersion', key, [dm.vars['dispersion'].value])
    

def fit(dm, method='map', param_type='prevalence', units='(per 1.0)', emp_prior={}):
    """ Generate an estimate of the beta binomial model parameters
    using maximum a posteriori liklihood (MAP) or Markov-chain Monte
    Carlo (MCMC).

    Parameters
    ----------
    dm : dismod3.DiseaseModel
      The object containing all the data, priors, and additional
      information (like input and output age-mesh).

    method : string, optional
      The parameter estimation method, either 'map' or 'mcmc'.

    param_type : str, optional
      Only data in dm.data with clean(d['data_type']).find(param_type) != -1
      will be included in the beta-binomial liklihood function.

    units : str, optional
      The units of this parameter, for pretty plotting, etc.

    emp_prior : dict, optional
      the empirical prior dictionary, retrieved from the disease model
      if appropriate by::

          >>> t, r, y, s = type_region_year_sex_from_key(key)
          >>> emp_prior = dm.get_empirical_prior(t)

    Example
    -------
    >>> import dismod3
    >>> import dismod3.beta_binomial_model as model
    >>> dm = dismod3.get_disease_model(1)
    >>> model.fit(dm, method='map', param_type='excess-mortality', units='(per person-year)')
    >>> model.fit(dm, method='mcmc', param_type='excess-mortality', units='(per person-year)')
    """

    # setup model variables, if they do not already exist
    if not hasattr(dm, 'vars'):
        data =  [d for d in dm.data if clean(d['data_type']).find(param_type) != -1]
        # use a random subset of the data if there is a lot of it,
        # to speed things up
        if len(data) > 25:
            dm.fit_initial_estimate(param_type, random.sample(data,25))
        else:
            dm.fit_initial_estimate(param_type, data)

        dm.set_units(param_type, units)

        dm.vars = setup(dm, param_type, data, emp_prior)

    # fit the model, with the selected method
    if method == 'map':
        if not hasattr(dm, 'map'):
            dm.map = mc.MAP(dm.vars)
        dm.map.fit(method='fmin_powell', iterlim=500, tol=.001, verbose=1)
        dm.set_map(param_type, dm.vars['rate_stoch'].value)
    elif method == 'mcmc':
        if not hasattr(dm, 'mcmc'):
            dm.mcmc = mc.MCMC(dm.vars)
        if len(dm.vars['latent_p']) > 0:
            dm.mcmc.use_step_method(mc.AdaptiveMetropolis, dm.vars['latent_p'])
        dm.mcmc.sample(iter=40000, burn=10000, thin=30, verbose=1)
        store_mcmc_fit(dm, param_type, dm.vars['rate_stoch'])


def store_mcmc_fit(dm, key, rate_stoch):
    """ Store the parameter estimates generated by an MCMC fit of the
    beta-binomial model in the disease_model object, keyed by key
    
    Parameters
    ----------
    dm : dismod3.DiseaseModel
      the object containing all the data, priors, and additional
      information (like input and output age-mesh)

    key : str

    rate_stoch : PyMC stochastic or deterministic variable

    Results
    -------
    Save a sketch of the distribution of rate_stoch keyed by key.

    Notes
    -----
    This method will be used by other models that have beta binomial
    parts as building blocks, so don't simplify the parameters, at
    least not without thinking about where else the function might
    need to be used
    """
    rate = rate_stoch.trace()
    trace_len = len(rate)
    age_len = len(dm.get_estimate_age_mesh())
    
    sr = []
    # TODO: use rate_stoch.stats() to get these statistics, instead of roll-me-own
    for ii in xrange(age_len):
        sr.append(sorted(rate[:,ii]))
    dm.set_mcmc('lower_ui', key, [sr[ii][int(.025*trace_len)] for ii in xrange(age_len)])
    dm.set_mcmc('median', key, [sr[ii][int(.5*trace_len)] for ii in xrange(age_len)])
    dm.set_mcmc('upper_ui', key, [sr[ii][int(.975*trace_len)] for ii in xrange(age_len)])
    dm.set_mcmc('mean', key, np.mean(rate, 0))

    if dm.vars[key].has_key('dispersion'):
        dm.set_mcmc('dispersion', key, dm.vars[key]['dispersion'].stats()['quantiles'].values())

def setup(dm, key, data_list, rate_stoch=None, emp_prior={}):
    """ Generate the PyMC variables for a beta binomial model of
    a single rate function

    Parameters
    ----------
    dm : dismod3.DiseaseModel
      the object containing all the data, priors, and additional
      information (like input and output age-mesh)
      
    key : str
      the name of the key for everything about this model (priors,
      initial values, estimations)

    data_list : list of data dicts
      the observed data to use in the beta-binomial liklihood function

    rate_stoch : pymc.Stochastic, optional
      a PyMC stochastic (or deterministic) object, with
      len(rate_stoch.value) == len(dm.get_estimation_age_mesh()).
      This is used to link beta-binomial stochs into a larger model,
      for example.

    emp_prior : dict, optional
      the empirical prior dictionary, retrieved from the disease model
      if appropriate by::

          >>> t, r, y, s = type_region_year_sex_from_key(key)
          >>> emp_prior = dm.get_empirical_prior(t)
      

    Results
    -------
    vars : dict
      Return a dictionary of all the relevant PyMC objects for the
      beta binomial model.  vars['rate_stoch'] is of particular
      relevance; this is what is used to link the beta-binomial model
      into more complicated models, like the generic disease model.

    Details
    -------
    The beta binomial model parameters are the following:
      * the mean age-specific rate function
      * dispersion of this mean
      * the p_i value for each data observation that has a standard
        error (data observations that do not have standard errors
        recorded are fit as observations of the beta r.v., while
        observations with standard errors recorded have a latent
        variable for the beta, and an observed binomial r.v.).
    """
    vars = {}
    est_mesh = dm.get_estimate_age_mesh()
    if np.any(np.diff(est_mesh) != 1):
        raise ValueError, 'ERROR: Gaps in estimation age mesh must all equal 1'

    # set up age-specific rate function, if it does not yet exist
    if not rate_stoch:
        param_mesh = dm.get_param_age_mesh()

        if emp_prior.has_key('mu'):
            initial_value = emp_prior['mu']
        else:
            initial_value = dm.get_initial_value(key)

        # find the logit of the initial values, which is a little bit
        # of work because initial values are sampled from the est_mesh,
        # but the logit_initial_values are needed on the param_mesh
        logit_initial_value = mc.logit(
            interpolate(est_mesh, initial_value, param_mesh))
        
        logit_rate = mc.Normal('logit(%s)' % key,
                               mu=-5.*np.ones(len(param_mesh)),
                               tau=1.e-2,
                               value=logit_initial_value)
        #logit_rate = [mc.Normal('logit(%s)_%d' % (key, a), mu=-5., tau=1.e-2) for a in param_mesh]
        vars['logit_rate'] = logit_rate

        @mc.deterministic(name=key)
        def rate_stoch(logit_rate=logit_rate):
            return interpolate(param_mesh, mc.invlogit(logit_rate), est_mesh)

    if emp_prior.has_key('mu'):
        @mc.potential(name='empirical_prior_%s' % key)
        def emp_prior_potential(f=rate_stoch, mu=emp_prior['mu'], tau=1./np.array(emp_prior['se'])**2):
            return mc.normal_like(f, mu, tau)
        vars['empirical_prior'] = emp_prior_potential


    vars['rate_stoch'] = rate_stoch

    # create stochastic variable for over-dispersion "random effect"
    mu_od = emp_prior.get('dispersion', .001)
    dispersion = mc.Gamma('dispersion_%s' % key, alpha=10., beta=10. / mu_od)
    vars['dispersion'] = dispersion
    
    @mc.deterministic(name='alpha_%s' % key)
    def alpha(rate=rate_stoch, dispersion=dispersion):
        return rate / dispersion ** 2
    @mc.deterministic(name='beta_%s' % key)
    def beta(rate=rate_stoch, dispersion=dispersion):
        return (1. - rate) / dispersion ** 2
    vars['alpha'] = alpha
    vars['beta'] = beta

    # create potentials for priors
    vars['priors'] = generate_prior_potentials(dm.get_priors(key), est_mesh, rate_stoch, dispersion)

    # create latent and observed stochastics for data
    vars['data'] = data_list
    vars['ab'] = []
    vars['latent_p'] = []
    vars['observations'] = []

    for d in data_list:
        # set up observed stochs for all relevant data
        id = d['id']
        
        if d['value'] == MISSING:
            print 'WARNING: data %d missing value' % id
            continue

        # ensure all rate data is valid
        d_val = dm.value_per_1(d)
        d_se = dm.se_per_1(d)
        
        if d_val < 0 or d_val > 1:
            print 'WARNING: data %d not in range [0,1]' % id
            continue

        if d['age_start'] < est_mesh[0] or d['age_end'] > est_mesh[-1]:
            raise ValueError, 'Data %d is outside of estimation range---([%d, %d] is not inside [%d, %d])' \
                % (d['id'], d['age_start'], d['age_end'], est_mesh[0], est_mesh[-1])

        age_indices = indices_for_range(est_mesh, d['age_start'], d['age_end'])
        age_weights = d['age_weights']

        @mc.deterministic(name='a_%d^%s' % (id, key))
        def a_i(alpha=alpha, age_indices=age_indices, age_weights=age_weights):
            return rate_for_range(alpha, age_indices, age_weights)
        @mc.deterministic(name='b_%d^%s' % (id, key))
        def b_i(beta=beta, age_indices=age_indices, age_weights=age_weights):
            return rate_for_range(beta, age_indices, age_weights)
        vars['ab'] += [a_i, b_i]
        
        if d_se > 0:
            # if the data has a standard error, model it as a realization
            # of a beta binomial r.v.
            latent_p_i = mc.Beta('latent_p_%d^%s' % (id, key), alpha=a_i, beta=b_i, value=trim(d_val, NEARLY_ZERO, 1-NEARLY_ZERO))
            vars['latent_p'].append(latent_p_i)

            denominator = d_val * (1 - d_val) / d_se**2.
            numerator = d_val * denominator
            obs_binomial = mc.Binomial('data_%d^%s' % (id, key), value=numerator, n=denominator, p=latent_p_i, observed=True)
            vars['observations'].append(obs_binomial)
        else:
            # if the data is a point estimate with no uncertainty
            # recorded, model it as a realization of a beta r.v.
            obs_p_i = mc.Beta('latent_p_%d' % id, value=trim(d_val, NEARLY_ZERO, 1-NEARLY_ZERO),
                              alpha=a_i, beta=b_i, observed=True)
            vars['observations'].append(obs_p_i)
        
    return vars
