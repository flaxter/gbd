"""
utility functions that several views will use.
"""
import StringIO
import csv

import pylab as pl

MIMETYPE = {'png': 'image/png',
            'svg': 'image/svg+xml',
            'eps': 'application/postscript',
            'ps': 'application/postscript',
            'pdf': 'application/pdf',
            'csv': 'text/csv',
            'json': 'application/json',
            }

command_list = {'edit': ['edit'],
                'move': ['prev', 'next'],
                'sex': ['male', 'female', 'total'],
                'format': ['png', 'svg', 'pdf', 'csv', 'json'],
                }

id_delta = {'prev': -1, 'next': 1}

def template_params(object, **params):
    template_params = {'command_list': command_list, 'id': object.id, 'obj': object}
    template_params.update(params)
    return template_params

def figure_data(format):
    """
    return a string containing the representation of the current
    matplotlib figure.  format must be something matplotlib
    understands
    """
    f = StringIO.StringIO()
    pl.savefig(f, format=format)
    f.seek(0)
    return f.read()


def csv_str(headings, rows):
    """
    return a string containing a csv version of the table with the
    given headings and row data
    """
    f = StringIO.StringIO()
    csv_writer = csv.writer(f)
    csv_writer.writerow(headings)
    csv_writer.writerows(rows)
    f.seek(0)
    return f.read()

def clear_plot(width=4*1.5, height=3*1.5):
    fig = pl.figure(figsize=(width,height))
    pl.clf()
    return fig

def label_plot(title, **params):
    pl.xlabel('Age (years)', **params)
    pl.ylabel('Rate (per 1.0)', **params)
    pl.title(str(title), **params)


def max_min_str(num_list):
    """ Return a nicely formated string denoting the range of a list of
    numbers.
    """
    if len(num_list) == 0:
        return '-'
    
    a = min(num_list)
    b = max(num_list)
    if a == b:
        return '%d' % a
    else:
        return '%d-%d' % (a,b)

SEPARATION_STR = '_'

def objects_to_id_str(objs):
    return SEPARATION_STR.join([str(o.id) for o in objs])

def id_str_to_objects(id_str, obj_class):
    id_list = [int(id) for id in id_str.split(SEPARATION_STR)]
    return obj_class.objects.filter(id__in=id_list)


PER_PAGE = 50

def paginated_models(request, models_filter):
    """
    return a list of paginated objects, chosen from the models_filter and
    the page param of the get request.
    """
    from django.core.paginator import Paginator, InvalidPage, EmptyPage

    paginator = Paginator(models_filter, per_page=PER_PAGE)
    
    # Make sure page request is an int. If not, deliver first page.
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
                            
    try:
        models = paginator.page(page)
    except (EmptyPage, InvalidPage):
        models = paginator.page(paginator.num_pages)

    return models
