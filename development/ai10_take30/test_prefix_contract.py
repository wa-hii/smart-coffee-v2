"""Offline regression of prefix features and fail-closed 300 sample validator."""
import unittest
import numpy as np
from benchmark_prefix import extract, ADC_COLUMNS
from candidate_diagnostic import features300, check_rows

def rows(n):
    return [{'cycle':i//30+1,'phase':'purging' if i%30<25 else 'collecting','sample_idx':i%30+1 if i%30<25 else i%30-24,'timestamp':1000*(i+1),**{s:1000+j+i%30 for j,s in enumerate(ADC_COLUMNS)}} for i in range(n*30)]

class Contract(unittest.TestCase):
    def test_300_valid(self):
        a=rows(30);v=check_rows(a,30);self.assertTrue(np.allclose(features300(a[:300]),extract(v,10)['raw3']))
    def test_prefix_no_future(self):
        v=check_rows(rows(30),30);before=extract(v,10)
        v[10:]=30000
        for name,values in before.items():np.testing.assert_array_equal(values,extract(v,10)[name])
    def test_wrong_length(self):
        a=rows(30)
        for count in (0,299,301,900):
            with self.assertRaises(ValueError):features300(a[:count])
    def test_bad_record(self):
        for key,value in [('phase','collecting'),('cycle',2),('sample_idx',2),('timestamp',-1),('adc_tgs822',float('nan')),('adc_mq8',-1),('adc_tgs816',32768)]:
            a=rows(10);a[0][key]=value
            with self.assertRaises(ValueError):features300(a)
    def test_duplicate_timestamp(self):
        a=rows(10);a[1]['timestamp']=a[0]['timestamp']
        with self.assertRaises(ValueError):features300(a)
if __name__=='__main__':unittest.main(verbosity=2)
