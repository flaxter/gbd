import numpy as np
import pymc as mc
from pymc import gp

import twill.commands as twc
import simplejson as json

from dismod3.settings import *
from dismod3.utils import debug, clean, trim, uninformative_prior_gp, prior_dict_to_str, NEARLY_ZERO, MAX_AGE, MISSING

class DiseaseJson:
    def __init__(self, json_str):
        dm = json.loads(json_str)
        self.params = dm['params']
        self.data = dm['data']
        self.id = dm.get('id',-1)
        self.extract_params_from_global_priors()

    def to_json(self):
        return json.dumps({'params': self.params, 'data': self.data, 'id': self.id})

    def merge(self, more_dm):
        """ merge all params from more_dm into self"""
        for key,val in more_dm.params.items():
            if isinstance(val, dict):
                if not key in self.params:
                    self.params[key] = {}
                self.params[key].update(val)
            else:
                self.params[key] = val

    def merge_posteriors(self, region='*'):
        """ merge model fit data into a DiseaseJson object
        region : str
          a regex string for which region posteriors to merge
        """
        dir = JOB_WORKING_DIR % self.id

        #fname = '%s/json/dm-%d-posterior-%s-%s-%s.json' % (dir, id, r,s,y)   # TODO: refactor naming into its own function
        import glob
        for fname in glob.glob('%s/json/*posterior*%s*.json' % (dir, region)):
            try:
                debug('merging %s' % fname)
                f = open(fname)
                self.merge(DiseaseJson(f.read()))
                f.close()
            except (ValueError, IOError):
                debug('failed to merge in %s' % fname)

    def save(self, fname='', keys_to_save=None):
        """ save results to json file
        remove extraneous keys (and all data) if requested"""

        if keys_to_save:
            # remove all keys that have not been changed by running this model
            # this prevents overwriting estimates that are being generated simulatneously
            # by other nodes in a cluster
            for k in self.params.keys():
                if type(self.params[k]) == dict:
                    for j in self.params[k].keys():
                        if not j in keys_to_save:
                            self.params[k].pop(j)

            # also remove data
            self.data = []

        # save results to json file
        debug('saving results')
        dir = JOB_WORKING_DIR % self.id
        if fname == '':
            fname = 'dm-%s.json' % self.id

        
        f = open('%s/json/%s' % (dir, fname), 'w')
        f.write(self.to_json())
        f.close()

    def savefig(self, fname):
        """ save figure in png subdir"""
        debug('saving figure %s' % fname)
        dir = JOB_WORKING_DIR % self.id
        from pylab import savefig, close
        try:
            savefig('%s/image/%s' % (dir, fname))
        except:
            debug('saving figure failed: %s/image/%s' % (dir, fname))
            f = open('%s/image/%s.txt' % (dir, fname), "w") 
	    f.write("ok\n")
	    f.close()
        close()

    def set_region(self, region):
        """ Set the region of the disease model"""
        self.params['region'] = region
    def get_region(self):
        """ Get the region of the disease model"""
        return self.params.get('region', '')

    def set_ymax(self, val):
        """ Set the maximum y scale for plotting the disease model"""
        self.params['ymax'] = val
    def get_ymax(self):
        """ Get the maximum y scale for plotting the disease model"""
        return self.params.get('ymax', 1.)

    def set_notes(self, val):
        """ Set notes for the disease model"""
        self.params['notes'] = val
    def get_notes(self):
        """ Get notes for the disease model"""
        return self.params.get('notes', '')

    def set_covariates(self, covariate_dict):
        self.params['covariates'] = covariate_dict
    def get_covariates(self):
        return self.params.get('covariates', {'Study_level':{}, 'Country_level':{}})

    def set_condition(self, val):
        """ Set notes for the disease model"""
        self.params['condition'] = val
    def get_condition(self):
        """ Get notes for the disease model"""
        return self.params.get('condition', 'unspecified')
        
    def set_key_by_type(self, key, type, value):
        if not self.params.has_key(key):
            self.params[key] = {}
        self.params[key][type] = value
    def get_key_by_type(self, key, type, default=None):
        return self.params.get(key, {}).get(type, default)
    def clear_key(self, key):
        if self.params.has_key(key):
            self.params.pop(key)

    def get_initial_value(self, type, default_val=None):
        """ Return the initial value for estimate of a particular
        type, default to NEARLY_ZERO"""
        if default_val == None:
            default_val = NEARLY_ZERO * np.ones(len(self.get_estimate_age_mesh()))
        return np.array(
            self.get_key_by_type('initial_value', type, default=default_val)
            )
    def set_initial_value(self, type, val):
        self.set_key_by_type('initial_value', type, list(val))
    def has_initial_value(self, type):
        return self.params.get('initial_value', {}).has_key(type)

    def get_map(self, type):
        return np.array(self.get_key_by_type('map', type, default=[]))
    def set_map(self, type, val):
        self.set_key_by_type('map', type, list(val))
    def has_map(self, type):
        return self.params.get('map', {}).has_key(type)

    def get_truth(self, type):
        return np.array(self.get_key_by_type('truth', type, default=[]))
    def set_truth(self, type, val):
        self.set_key_by_type('truth', type, list(val))
    def has_truth(self, type):
        return self.params.get('truth', {}).has_key(type)

    def get_mcmc(self, est_type, data_type):
        val = self.get_key_by_type('mcmc_%s' % est_type, data_type, default=[])

        # TODO: sometimes an mcmc_upper_ui key is set to {}, which is wrong and needs debugged
        if val == {}:
            val = []
        return np.array(val)
    def set_mcmc(self, est_type, data_type, val):
        self.set_key_by_type('mcmc_%s' % est_type, data_type, list(val))
    def has_mcmc(self, type):
        return self.params.get('mcmc_mean', {}).has_key(type)

    def get_population(self, region):
        return np.array(self.get_key_by_type('population', region, default=np.ones(MAX_AGE)))
        #return np.array(self.get_key_by_type('population', region, default=None))
    def set_population(self, region, val):
        self.set_key_by_type('population', region, list(val))

    def clear_fit(self):
        """ Clear all estimates, fits, and stochastic vars

        Results
        -------
        disease_model.clear_fit() removes all the results of a fit, so
        that the model is ready for fitting fresh, for example with
        different new priors

        Example
        -------
        >>> import dismod3
        >>> dm = dismod3.get_disease_model(1)
        >>> dm.clear_fit()
        """
        for k in self.params.keys():
            if k == 'map' or k.find('mcmc_') >= 0:
                self.params.pop(k)

        if hasattr(self, 'vars'):
            delattr(self, 'vars')
            
        if hasattr(self, 'map'):
            delattr(self, 'map')
            
        if hasattr(self, 'mcmc'):
            delattr(self, 'mcmc')

    def get_units(self, type):
        return self.get_key_by_type('units', type)
    def set_units(self, type, units):
        self.set_key_by_type('units', type, units)

    def get_priors(self, type):
        """ Return the priors for estimates of given type

        If no specific priors are found for the given type, default to the
        value in get_global_priors(type)
        """
        prior_str = self.get_key_by_type('priors', type, default='')
        if not prior_str:
            type = type.split(KEY_DELIM_CHAR)[0]
            prior_str = self.get_global_priors(type)
        return prior_str
    
    def set_priors(self, type, priors):
        """ Set the prior for data of a given type

        Parameters
        ----------
        type : str
          The type of data to which these priors apply
        priors : str
          The priors, see the prior generating function for details

        Notes
        -----
        Any stochastic variables are deleted, since they do not
        include the new priors
        """
        self.set_key_by_type('priors', type, priors)
        self.clear_fit()

    def get_global_priors(self, type):
        """ Return the global priors that best match the specified type

        Since the type might be a key with the form
        'incidence+sub-saharan_africa_east+1990+female', return the
        first global prior who's key is found as a substring of ``type``

        Build and cache the global_priors_dict from the
        global_priors_json, if necessary.
        """
        if not hasattr(self, 'global_priors'):
            raw_dict = self.params.get('global_priors', {})
            self.global_priors = {'prevalence': {},
                                  'incidence': {},
                                  'remission': {},
                                  'excess_mortality': {},
                                  'relative_risk': {},
                                  'duration': {},
                                  }

            # reverse the order of the first and second level of keys in the raw_dict
            # this will be more convenient later
            for k1 in ['heterogeneity', 'smoothness', 'level_value', 'level_bounds', 'increasing', 'decreasing', 'unimodal']:
                if not raw_dict.has_key(k1):
                    continue
                for k2 in raw_dict[k1]:
                    self.global_priors[k2][k1] = raw_dict[k1][k2]

            # deal with the dash vs underscore
            self.global_priors['excess-mortality'] = self.global_priors['excess_mortality']
            self.global_priors['relative-risk'] = self.global_priors['relative_risk']
            
            for k in self.global_priors:
                self.global_priors[k]['prior_str'] = prior_dict_to_str(self.global_priors[k])
        for k in self.global_priors:
            if clean(type) == clean(k):
                return self.global_priors[k]['prior_str']

        return ''

    def extract_params_from_global_priors(self):
        """ The global priors hash contains information on the age mesh,
        max y value, and additional notes, which should be stored
        somewhere more convenient
        """
        if self.params.has_key('global_priors'):
            gp_dict = self.params['global_priors']
            if gp_dict.has_key('parameter_age_mesh'):
                self.set_param_age_mesh([int(a) for a in gp_dict['parameter_age_mesh']])
                self.set_ymax(float(gp_dict['y_maximum']))
                self.set_notes(gp_dict['note'])

    def set_empirical_prior(self, type, prior_dict):
        """ The empirical prior hash contains model-specific data for
        keyed by model parameter types"""
        self.params['empirical_prior_%s' % type] = json.dumps(prior_dict)
    def clear_empirical_prior(self):
        """ Remove empirical priors for all keys"""
        self.clear_key('empirical_prior')
        self.clear_key('mcmc_emp_prior_mean')
        self.clear_key('mcmc_lower_ui')
        self.clear_key('mcmc_upper_ui')
    def get_empirical_prior(self, type):
        """ The empirical prior is a model specific dictionary

        to check if empirical priors of a particular rate type exist for a DiseaseJson, use this::

            dm.get_empirical_prior(type)

        if the result is an empty dict, there is no empirical prior.

        if there is an empirical prior, the result will be a dict with keys including::

            ['sigma_gamma', 'sigma_alpha', 'sigma_beta', 'beta', 'sigma_delta', 'delta', 'alpha', 'gamma']
        """
        return json.loads(self.params.get('empirical_prior_%s' % type, '{}'))

    def get_estimate_age_mesh(self):
        return self.params.get('estimate_age_mesh', range(MAX_AGE))
    def set_estimate_age_mesh(self, mesh):
        """ Set the age mesh for the estimated age functions

        Parameters
        ----------
        mesh : list
          The estimate mesh.  Estimates for the prevalence, incidence,
          etc will be estimated at each point on this mesh.  For the
          generic disease model, the distance between consecutive mesh
          points must be one.

        Notes
        -----
        Any stochastic variables are deleted, since they need to be
        regenerated to reflect the new age mesh
        """
        self.params['estimate_age_mesh'] = list(mesh)
        
    def get_param_age_mesh(self):
        return self.params.get('param_age_mesh', range(0, MAX_AGE, 10))
    def set_param_age_mesh(self, mesh):
        """ Set the age mesh for the age functions control parameters

        Parameters
        ----------
        mesh : list
          The param mesh, the values at these mesh points will be
          linearly interpolated to form the age-specific function

        Notes
        -----
        To save time, the stochastic models use a linear interpolation
        of the points on the param age mesh to represent the age
        function.
        
        Any stochastic variables are deleted, since they need to be
        regenerated to reflect the new age mesh
        """
        self.params['param_age_mesh'] = list(mesh)
        
    def set_model_source(self, source_obj):
        try:
            import inspect
            self.params['model_source'] = inspect.getsource(source_obj)
        except:
            self.params['model_source'] = '(failed to read file)'
    def get_model_source(self):
        return self.params.get('model_source', '')
    
    def filter_data(self, data_type=None, sex=None):
        return [d for d in self.data if ((not data_type) or d['data_type'] == data_type) \
                    and ((not sex) or d['sex'] == sex)
                ]
    def extract_units(self, d):
        """
        d is a data hash which might include
        the key 'units', which is a decription
        of the units for this datum.
        
        return the float that d['value'] should
        be multiplied to make the units per 1.0

        TODO: migrate to using 'radix', a number with no 'per '
        business

        This is hacky, so examples are best for now

        Example
        -------
        >>> dm.extract_units({})
        1.
        >>> dm.extract_units({'units': 'per 10'})
        .1
        >>> dm.extract_units({'units': '10'})
        .1
        >>> dm.extract_units({'units': 'bananas'})
        1.
        
        """
        try:
            unit_str = d.get('units', '1')
            unit_str = unit_str.replace('per ', '')
            unit_str = unit_str.replace(',', '')
            units = 1. / float(unit_str)
            return units
        except ValueError:
            debug('could not parse unit str: %s' % unit_str)
            return 1.


    def mortality(self, key='all-cause_mortality', data=None):
        """ Calculate the all-cause mortality rate for the
        region and sex of disease_model, and return it
        in an array corresponding to age_mesh

        Parameters
        ----------
        key : str, optional
          of the form 'all-cause_mortality+gbd_region+year+sex'
        data: list, optional
          the data list to extract all-cause mortality from
        """
        if self.params.get('initial_value',{}).has_key(key):
            return self.get_initial_value(key)

        if not data:
            data = self.filter_data('all-cause_mortality data')
        
        if len(data) == 0:
            return NEARLY_ZERO * np.ones(len(self.get_estimate_age_mesh()))
        else:
            M,C = uninformative_prior_gp(c=-1., scale=300.)
            age = []
            val = []
            V = []
            for d in data:
                scale = self.extract_units(d)
                a0 = d.get('age_start', MISSING)
                a1 = d.get('age_end', MISSING)
                y = self.value_per_1(d)
                se = self.se_per_1(d)

                if se == MISSING:
                    se = .01
                if MISSING in [a0, a1, y]:
                    continue


                age.append(.5 * (a0 + a1))
                val.append(y + .00001)
                V.append(se ** 2.)

            if len(data) > 0:
                gp.observe(M, C, age, mc.logit(val), V)

            normal_approx_vals = mc.invlogit(M(self.get_estimate_age_mesh()))
            self.set_initial_value(key, normal_approx_vals)
            return self.get_initial_value(key)

    def value_per_1(self, data):
        if data['value'] == MISSING:
            return MISSING

        return data['value'] * self.extract_units(data)

    def se_per_1(self, d):
        se = MISSING

        if d['standard_error'] != MISSING:
            se = d['standard_error']
            se *= self.extract_units(d)
        else:
            try:
                n = float(d['effective_sample_size'])
                p = self.value_per_1(d)
                se = np.sqrt(p*(1-p)/n)
            except (ValueError, KeyError):
                try:
                    lb = float(d['lower_ci']) * self.extract_units(d)
                    ub = float(d['upper_ci']) * self.extract_units(d)
                    se = (ub-lb)/(2*1.96)
                except (ValueError, KeyError):
                    pass

        return se

    def bounds_per_1(self, d):
        val = self.value_per_1(d)
        try:
            lb = float(d['lower_ci']) * self.extract_units(d)
            ub = float(d['upper_ci']) * self.extract_units(d)

            return lb, ub
        except (KeyError, ValueError):
            pass

        try:
            lb = float(d['lower_cl']) * self.extract_units(d)
            ub = float(d['upper_cl']) * self.extract_units(d)
                
            return lb, ub
        except (KeyError, ValueError):
            pass

        se = self.se_per_1(d)
        if se != MISSING:
            return val - 1.96*se, val + 1.96*se
        else:
            return MISSING, MISSING
        

    def calc_effective_sample_size(self, data):
        """ calculate effective sample size for data that doesn't have it"""
        for d in data:
            if d.has_key('effective_sample_size') and d['effective_sample_size']:
                d['effective_sample_size'] = float(str(d['effective_sample_size']).replace(',', ''))
                continue

            Y_i = self.value_per_1(d)
            # TODO: allow Y_i > 1, extract effective sample size appropriately in this case
            if Y_i < 0 or Y_i > 1:
                debug('WARNING: data %d not in range (0,1)' % d['id'])
                d['effective_sample_size'] = 1.
                continue

            se = self.se_per_1(d)

            # TODO: if se is missing calc effective sample size from the bounds_per_1
            if se == MISSING or se == 0. or Y_i == 0:
                N_i = 1.
            else:
                N_i = Y_i * (1-Y_i) / se**2

            d['effective_sample_size'] = N_i


    def fit_initial_estimate(self, key, data_list):
        """ Find an initial estimate of the age-specific data

        Parameters
        ----------
        key : str
          The name of the estimate, as used in
          self.set_initial_value(key) and
          self.get_inital_value(key).

        data_list : list of data dicts
          The data to use for creating the initial estimate.
          
        Results
        -------
        The estimated parameter values are stored using
        self.set_initial_value(key, values)

        Example
        -------
        >>> import dismod3
        >>> dm = dismod3.get_disease_model(1)
        >>> dm.find_initial_estimate('prevalence', dm.filter_data('prevalence data'))
        >>> dm.get_initial_value('prevalence')
        
        Notes
        -----
        This estimate for an age-specific dataset is formed by using
        each datum to produce an estimate of the function value at a
        single age, and then taking the inverse-variance weighted
        average.
        """
        x = self.get_estimate_age_mesh()
        y = np.zeros(len(x))
        N = np.zeros(len(x))

        self.calc_effective_sample_size(data_list)

        for d in data_list:
            y[d['age_start']:(d['age_end']+1)] += self.value_per_1(d) * d['effective_sample_size']
            N[d['age_start']:(d['age_end']+1)] += d['effective_sample_size']

        y = np.where(N > 0, y/N, 0)
        self.set_initial_value(key, y)
        
# to run a bunch of empirical prior fits programatically:
#for i in range(4091, 4108):
#    dismod3.disease_json.twc.go('http://winthrop.ihme.washington.edu/dismod/run/%d'%i)
#    dismod3.disease_json.twc.formvalue(2,2, 'run_page')
#    dismod3.disease_json.twc.submit()

import os
import random

def random_rename(fname):
    print "random rename %s"%fname
    os.rename(fname, fname + str(random.random())[1:])

def create_disease_model_dir(id):
    """ make directory structure to store computation output"""
    
    dir = JOB_WORKING_DIR % id
    if os.path.exists(dir):        # move to dir + random extension
        random_rename(dir)
    os.makedirs(dir)

    for phase in ['empirical_priors', 'posterior']:
        os.mkdir('%s/%s' % (dir, phase))
        for f_type in ['stdout', 'stderr', 'pickle']:
            os.mkdir('%s/%s/%s' % (dir, phase, f_type))
    os.mkdir('%s/json' % dir)
    os.mkdir('%s/image' % dir)

def keys2str(keys):
    # TODO: fix this hackery
    if len(keys) == 1:
        return '+'.join(keys)
    if len(keys) == 9:
        return 'all+' + '+'.join(keys[0][1:])
    raise Exception, 'keys2str not yet implemented for %s' % keys

def image_name(id, style, keys, format):
    key_str = keys2str(keys)
    return JOB_WORKING_DIR % id + '/image/' + '%d+%s+%s.%s' % (id, style, key_str, format)

def delete_image(id, style, keys, format):
    fname = image_name(id, style, keys, format)
    if os.path.exists(fname):
        random_rename(fname)

def image_exists(id, style, keys, format):
    fname = image_name(id, style, keys, format)
    return os.path.exists(fname)
  
def load_disease_model(id):
    """ return a DiseaseJson object 


    if the JOB_WORKING_DIR contains .json files, use them to construct
    the disease model
    
    if not, fetch specificed disease model data from
    dismod server given in settings.py
    """
    try:
        dir = JOB_WORKING_DIR % id
        fname = '%s/json/dm-%s.json' % (dir, id)
        f = open(fname)
        dm_json = f.read()
        dm = DiseaseJson(dm_json)  # TODO: handle error if json fails to load
        f.close()

        import glob
        for fname in sorted(glob.glob('%s/json/dm-%d*.json' % (dir, id)), reverse=True):
            try:
                debug('merging %s' % fname)
                f = open(fname)
                dm.merge(DiseaseJson(f.read()))
                f.close()

            except ValueError:
                debug('failed to merge in %s' % fname)
        return dm

    except IOError: # no local copy, so download from server
        return fetch_disease_model(id)

def fetch_disease_model(id):
    from twill import set_output
    set_output(open('/dev/null', 'w'))

    dismod_server_login()

    twc.go(DISMOD_DOWNLOAD_URL % id)
    result_json = twc.show()
    twc.get_browser()._browser._response.close()  # end the connection, so that apache doesn't get upset

    dm = DiseaseJson(result_json)
    return dm

def get_disease_model(id):
    """ legacy function: pass it on to fetch disease model"""
    return fetch_disease_model(id)

def try_posting_disease_model(dm, ntries):
    # error handling: in case post fails try again, but stop after 3 tries
    from twill.errors import TwillAssertionError
    import random
    import time

    url = ''
    for ii in range(ntries):
        try:
            url = post_disease_model(dm)
            break
        except TwillAssertionError:
            pass
        if ii < ntries-1:
            debug('posting disease model failed, retrying in a bit')
            time.sleep(random.random()*30)
        else:
            debug('posting disease model failed %d times, giving up' % (ii+1))

    twc.get_browser()._browser._response.close()  # end the connection, so that apache doesn't get upset
    return ''

def post_disease_model(disease):
    """
    fetch specificed disease model data from
    dismod server given in settings.py
    """
    dismod_server_login()

    # don't upload the disease data, since it is already on the server
    data = disease.data
    disease.data = []
    d_json = disease.to_json()
    disease.data = data
    
    twc.go(DISMOD_UPLOAD_URL)
    twc.fv('1', 'model_json', d_json)
    twc.submit()


def add_covariates_to_disease_model(dm):
    """
    submit request to dismod server to add covariates to disease model dm
    wait for response (which can take a while)
    """
    dismod_server_login()

    twc.go(DISMOD_BASE_URL + 'dismod/run/%d' % dm)
    twc.fv('1', 'update', '')
    twc.submit()


def get_job_queue():
    """
    fetch list of disease model jobs waiting to run from dismod server
    given in settings.py.
    """
    dismod_server_login()
    twc.go(DISMOD_LIST_JOBS_URL)
    return json.loads(twc.show())

def remove_from_job_queue(id):
    """
    remove a disease model from the job queue on the dismod server
    given in dismod3/settings.py
    """
    dismod_server_login()
    
    twc.go(DISMOD_REMOVE_JOB_URL)
    twc.fv('1', 'id', str(id))
    twc.submit()
    return json.loads(twc.show())
    

def dismod_server_login():
    """ login to the dismod server given in dismod3/settings.py."""
    
    twc.go(DISMOD_LOGIN_URL)
    twc.fv('1', 'username', DISMOD_USERNAME)
    twc.fv('1', 'password', DISMOD_PASSWORD)
    twc.submit()
    twc.url('accounts/profile')
    
def init_job_log(id, estimate_type, param_id):
    """
    initialize job log in the job status file on the webserver.
    """
    twc.go(DISMOD_INIT_LOG_URL % (id, estimate_type, param_id))

def log_job_status(id, estimate_type, fitting_task, state):
    """
    log job status in the job status file on the webserver.
    """
    twc.go(DISMOD_LOG_STATUS_URL % (id, estimate_type, fitting_task, state))
