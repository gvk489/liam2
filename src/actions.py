import os
import csv

import numpy as np

from expr import functions, Expr, expr_eval
import simulation
from properties import Process, BreakpointException


class Show(Process):
    def __init__(self, *args):
        Process.__init__(self)
        self.args = args

    def run(self, context):
        if simulation.skip_shows:
            print "skipped",
        else:
            values = [expr_eval(expr, context) for expr in self.args]
            print ' '.join(str(v) for v in values),

    def __str__(self):
        #TODO: the differenciation shouldn't be needed. I guess I should
        # have __repr__ defined for all properties
        str_args = [str(arg) if isinstance(arg, Expr) else repr(arg)
                    for arg in self.args]
        return 'show(%s)' % ', '.join(str_args) 


class CSV(Process):
    def __init__(self, expr, suffix='', fname=None, mode='w'):
        self.expr = expr
        #TODO: make base class for Dump & GroupBy
#        assert isinstance(expr, (Dump, GroupBy))
        if fname is not None and suffix:
            raise ValueError("csv() can't have both 'suffix' and 'fname' "
                             "arguments")
        self.suffix = suffix
        self.fname = fname
        if mode not in ('w', 'a'):
            raise ValueError("csv() mode argument should be either " 
                             "'w' (overwrite) or 'a' (append)")
        self.mode = mode

    def run(self, context):
        entity = context['__entity__']
        period = context['period']
        if self.fname is not None:
            fname = self.fname.format(entity=entity.name, period=period)
        elif self.suffix:
            #XXX: in py2.7, we can use {} instead
            fname = "{0}_{1}_{2}.csv".format(entity.name, period, self.suffix)
        else:
            #XXX: in py2.7, we can use {} instead
            fname = "{0}_{1}.csv".format(entity.name, period)

        print "writing to", fname, "...",          
        file_path = os.path.join(simulation.output_directory, fname)
        with open(file_path, self.mode + 'b') as f:
            data = expr_eval(self.expr, context)
            dataWriter = csv.writer(f)
            dataWriter.writerows(data)


class RemoveIndividuals(Process):
    def __init__(self, filter):
        Process.__init__(self)
        self.filter = filter

    def run(self, context):
        filter = expr_eval(self.filter, context)

        if not np.any(filter):
            return
        
        not_removed = ~filter
        
        entity = context['__entity__']
        len_before = len(entity.array)
        already_removed = entity.id_to_rownum == -1
        already_removed_indices = already_removed.nonzero()[0]
        already_removed_indices_shifted = already_removed_indices - \
                                  np.arange(len(already_removed_indices))

        # recreate id_to_rownum from scratch
        id_to_rownum = np.arange(len_before)
        id_to_rownum -= filter.cumsum()
        #XXX: use np.putmask(id_to_rownum, filter, -1)
        id_to_rownum[filter] = -1
        entity.id_to_rownum = np.insert(id_to_rownum,
                                        already_removed_indices_shifted,
                                        -1)
        #FIXME: this allocates a new (slightly smaller) array then the old 
        # array is discarded when the gc does its job, effectively doubling
        # the peak memory usage for the main array 
        entity.array = entity.array[not_removed]
        temp_variables = entity.temp_variables
        for name, temp_value in temp_variables.iteritems():
            if isinstance(temp_value, np.ndarray) and temp_value.shape:
                temp_variables[name] = temp_value[not_removed]

        print "%d %s(s) removed (%d -> %d)" % (filter.sum(), entity.name,
                                               len_before, len(entity.array)),
        

class Breakpoint(Process):
    def __init__(self, period=None):
        Process.__init__(self)
        self.period = period

    def run(self, context):
        if self.period is None or self.period == context['period']:
            raise BreakpointException()

    def __str__(self):
        return 'breakpoint(%d)' % self.period if self.period is not None else '' 


functions.update({
    # can't use "print" in python 2.x because it's a keyword, not a function        
#    'print': Print,
    'csv': CSV,
    'show': Show,
    'remove': RemoveIndividuals,
    'breakpoint': Breakpoint,
})