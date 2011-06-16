"""
This module provide the python shell interface to the generic disease
modeling system, as well as all of the parameters and functions
specific to the statistical modeling and plotting of generic disease.

see ``../docs/tutorial.rst`` for more details on the interface.
"""

from utils import gbd_regions, gbd_years, gbd_sexes, \
    data_types, gbd_key_for, type_region_year_sex_from_key

from utils import NEARLY_ZERO, MAX_AGE, MISSING, PRIOR_SEP_STR

from plotting import tile_plot_disease_model, sparkplot_disease_model, \
    sparkplot_boxes, overlay_plot_disease_model, plot_prior_preview, bar_plot_disease_model

from table import table_by_region_year_sex, table_by_region

from disease_json import get_job_queue, remove_from_job_queue, \
     try_posting_disease_model, post_disease_model, init_job_log, log_job_status, \
     fetch_disease_model, load_disease_model, get_disease_model, add_covariates_to_disease_model

from gbd_disease_model import relevant_to

from table import population_by_region_year_sex
