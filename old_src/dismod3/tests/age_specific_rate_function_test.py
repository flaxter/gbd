from base_test import DisModTestCase
from django.test.client import Client
import simplejson as json

from dismod3.models import *
from dismod3.views import *

class AgeSpecificRateFunctionTestCase(DisModTestCase):
    def setUp(self):
        self.disease = Disease.objects.get(name='Cannabis Use')
        self.region = Region.objects.get(name='Australasia')
        self.rate = Rate.objects.all()[0]
        self.asrf = AgeSpecificRateFunction.objects.all()[1]
        self.create_users()

    # unit tests
    def test_save(self):
        rf = AgeSpecificRateFunction(disease=self.disease, region=self.region, rate_type='prevalence data', sex='total')
        assert(rf.fit.has_key('age_mesh'))

        rf.save()
        self.assertEqual(rf.rates.count(), rf.num_rates)

    def test_strs(self):
        s = str(self.asrf)
        self.assertNotEqual(s, '')

        s = self.asrf.get_absolute_url()
        self.assertNotEqual(s, '')

    def test_clone(self):
        initial_count = AgeSpecificRateFunction.objects.count()
        new_asrf = self.asrf.clone('Cloned copy')
        self.assertEqual(AgeSpecificRateFunction.objects.count(), initial_count + 1)
        self.assertEqual(new_asrf.notes, 'Cloned copy')
        self.assertEqual(self.asrf.rates.count(), new_asrf.rates.count())

        # check that the cloned asrf does not have the fit data of the old one
        self.assertEqual(new_asrf.fit.get('mcmc_mean', None), None)
        self.assertEqual(new_asrf.fit.get('map', None), None)
        self.assertEqual(new_asrf.fit.get('mcmc_upper_cl', None), None)
        self.assertEqual(new_asrf.fit.get('mcmc_lower_cl', None), None)

    def test_fit(self):
        from dismod3.bayesian_models import fit_rate_function
        from dismod3.tests import bayesian_probability_test
        bayesian_probability_test.add_priors(self.asrf)
        fit_rate_function.mcmc_fit(self.asrf, speed='testing fast')

    # related rates finds all rates in the db that match the parameters of the asrf
    def test_related_rates(self):
        rates = self.asrf.relevant_rates()
        assert(rates.count() > 0)

    def test_create_multiple(self):
        # create asrf for specific disease, region, rate type, and sex
        asrfs = age_specific_rate_function.create_multiple(self.disease, self.region, rate_type='prevalence data', sex='total')
        self.assertEqual(len(asrfs), 1)
        assert(asrfs[0].rates.count() > 0)

        # create asrfs for all rate types and sexes
        asrfs = age_specific_rate_function.create_multiple(self.disease, self.region)
        self.assertEqual(len(asrfs), (len(fields.RATE_TYPE_CHOICES)-1)*len(fields.SEX_CHOICES))

        # create asrfs for all regions, rate types, and sexes
        asrfs = age_specific_rate_function.create_multiple(self.disease)
        self.assertEqual(len(asrfs), Region.objects.count()*(len(fields.RATE_TYPE_CHOICES)-1)*len(fields.SEX_CHOICES))

    def test_predict_rate(self):
        r = probabilistic_utils.predict_rate_from_asrf(self.asrf, self.rate)
        self.assertEqual(r, 0.)

    # functional tests
    def test_index_view(self):
        c = Client()
        c.login(username='red', password='red')
        response = c.get('/age_specific_rate_function/')
        self.assertTemplateUsed(response, 'age_specific_rate_function/index.html')

    def test_create_multiple_view(self):
        c = Client()
        c.login(username='red', password='red')

        # first try without a disease, should say the field is required
        response = c.post('/age_specific_rate_function/', {'disease': ['']} )
        self.assertContains(response, 'field is required')

        # try posting to creating new asrfs, and check if the total number increases
        asrf_cnt = AgeSpecificRateFunction.objects.count()
        response = c.post('/age_specific_rate_function/',
                          {'disease': [str(self.disease.id)], 'region': [str(self.region.id)],
                           'rate_type': 'prevalence data', 'sex': 'all', 'notes': ''} )

        # ensure that this actually created a number of new asrf objects
        self.assertEqual(AgeSpecificRateFunction.objects.all().count(), asrf_cnt + 3)

        id_str = view_utils.objects_to_id_str(AgeSpecificRateFunction.objects.all()[asrf_cnt:])
        redirect_url = '/age_specific_rate_function/%s' % id_str
        self.assertRedirects(response, redirect_url)
        
        # test the png version of the output
        response = c.get(redirect_url + '.png')
        self.assertEqual(response.status_code, 200)

    def test_redirect_view(self):
        c = Client()
        c.login(username='red', password='red')

        # try navigating through them
        response = c.get('/age_specific_rate_function/%d/png' % self.asrf.id)
        self.assertRedirects(response, '/age_specific_rate_function/%d.png' % self.asrf.id)

        response = c.get('/age_specific_rate_function/%d/prev' % self.asrf.id)
        self.assertRedirects(response, '/age_specific_rate_function/%d' % (self.asrf.id-1))

        response = c.get('/age_specific_rate_function/%d/next' % self.asrf.id)
        self.assertRedirects(response, '/age_specific_rate_function/%d' % (self.asrf.id+1))

    def test_ppc_view(self):
        c = Client()
        c.login(username='red', password='red')

        response = c.get('/age_specific_rate_function/posterior_predictive_check/%d_ppc_scatter.png' % self.asrf.id)
        self.assertPng(response)

        response = c.get('/age_specific_rate_function/posterior_predictive_check/%d_ppc_intervals.png' % self.asrf.id)
        self.assertPng(response)

    def test_sparkplot_view(self):
        c = Client()
        c.login(username='red', password='red')
        
        response = c.get('/age_specific_rate_function/asrf_%d_sparkplot.png' % self.asrf.id)
        self.assertPng(response)
    
    def test_clone_view(self):
        c = Client()
        c.login(username='red', password='red')

        # simulate a click on the clone button from a rate function page
        response = c.get('/age_specific_rate_function/%d/clone' % self.asrf.id)
        self.assertTemplateUsed(response, 'age_specific_rate_function/clone.html')
        self.assertContains(response, 'Priors')

        # simulate inputing notes and priors to the clone page
        initial_cnt = AgeSpecificRateFunction.objects.count()
        response = c.post('/age_specific_rate_function/%d/clone' % self.asrf.id,
                          {'notes': 'My Notes', 'priors': 'smooth 3.14'} )
        self.assertEqual(AgeSpecificRateFunction.objects.count(), initial_cnt+1)
        new_asrf = AgeSpecificRateFunction.objects.all()[(initial_cnt+1)-1]
        self.assertEqual(new_asrf.notes, 'My Notes')
        self.assertEqual(new_asrf.fit['priors'], 'smooth 3.14')
        self.assertRedirects(response, '/age_specific_rate_function/%d_%d' % (self.asrf.id, new_asrf.id))
        
    def test_compare_view(self):
        """
        the compare view is intended to do various visual comparison
        of two age specific rate functions

        supported styles:
          overlay
          scatter
          stack
          parallel
        """
        c = Client()
        c.login(username='red', password='red')

        response = c.get('/age_specific_rate_function/compare/1000_1001')
        self.assertTemplateUsed(response, 'age_specific_rate_function/compare.html')

        response = c.get('/age_specific_rate_function/compare/1000_1001_compare.png')
        self.assertPng(response)

        response = c.get('/age_specific_rate_function/compare/1000_1001_compare.png', {'style': 'scatter'})
        self.assertPng(response)

        response = c.get('/age_specific_rate_function/compare/1000_1001_compare.png', {'style': 'stack'})
        self.assertPng(response)

        response = c.get('/age_specific_rate_function/compare/1000_1001_compare.png', {'style': 'parallel'})
        self.assertPng(response)

    def test_show_view(self):
        """
        the show view supports arguments about subplot size and also
        about the axis, for zooming
        """

        c = Client()
        c.login(username='red', password='red')

        response = c.get('/age_specific_rate_function/1000')
        self.assertTemplateUsed(response, 'age_specific_rate_function/show.html')

        response = c.get('/age_specific_rate_function/1000.png')
        self.assertPng(response)

        response = c.get('/age_specific_rate_function/1000.png', {'xmax': '.0001'})
        self.assertPng(response)
