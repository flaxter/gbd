from base_test import DisModTestCase
from django.test.client import Client
import simplejson as json

from dismod3.models import *
from dismod3.views import *

class DiseaseModelTestCase(DisModTestCase):
    def setUp(self):
        self.disease = Disease.objects.get(name='Cannabis Use')
        self.region = Region.objects.get(name='Australasia')
        self.rate = Rate.objects.all()[0]
        self.asrf = AgeSpecificRateFunction.objects.all()[1]
        self.dm = DiseaseModel.objects.all()[0]
        self.create_users()

    ############
    # unit tests
    #
    def test_strs(self):
        s = str(self.dm)
        self.assertNotEqual(s, '')

        s = self.dm.get_absolute_url()
        self.assertNotEqual(s, '')

        s = self.dm.get_asrf_id_str()
        self.assertNotEqual(s, '')

    def test_fit(self):
        from dismod3.bayesian_models import fit_disease_model
        fit_disease_model.mcmc_fit(self.dm, speed='testing fast')

    ##################
    # functional tests
    #
    def test_index_view(self):
        c = Client()
        c.login(username='red', password='red')

        response = c.get('/disease_model/')
        self.assertTemplateUsed(response, 'disease_model/index.html')

        # test pagination
        response = c.get('/disease_model/', {'page': 2})
        self.assertTemplateUsed(response, 'disease_model/index.html')

        response = c.get('/disease_model/', {'page': 'fish'})
        self.assertTemplateUsed(response, 'disease_model/index.html')


    def test_show_view(self):
        """
        the show view could one day support arguments about subplot size and also
        about the axis, for zooming, which it can pass through to the rate function
        view
        """

        c = Client()
        c.login(username='red', password='red')

        response = c.get('/disease_model/%d' % self.dm.id)
        self.assertTemplateUsed(response, 'disease_model/show.html')

    def test_sparkplot_view(self):
        c = Client()
        c.login(username='red', password='red')

        response = c.get('/disease_model/dm_%d_sparkplot.png' % self.dm.id)
        self.assertPng(response)
        
