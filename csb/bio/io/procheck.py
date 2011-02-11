"""
Procheck parser

"""
import os
import re


class ProcheckInfo(dict):

    def get_rama_info(self):
        if 'rama_core' in self.keys():
            return [float(self['rama_core']),
                    float(self['rama_allow']),
                    float(self['rama_gener']),
                    float(self['rama_disall'])]
        else:
            return None
        

class ProcheckParser():
    """
    Simple Prochceck Summary parser
    """
    def __init__(self):
        self.binary = '/home/mechelke/install/procheck/procheck.scr'
    
    def run(self, pdb_file):

        wd = os.getcwd()
        tmp = tempfile.mkdtemp()
        base = os.path.basename(pdb_file)
        
        p = subprocess.call('cp %s %s/.' % (os.path.expanduser(pdbfile), tmp), shell = True)
        os.chdir(tmp)

        p = subprocess.Popen('%s %s 1.5' %(self.binary, os.path.join(tmp,base)),
                             stdout=open("/dev/null", "w"),
                             stderr=open("/dev/null", "w"),
                             shell = True)
        
        sts = os.waitpid(p.pid, 0)[1]
        summary = '.'.join([os.path.splitext(base)[0],'sum'])
        out = self.parse(os.path.join(tmp,summary))
        
        os.chdir(wd)
        p = subprocess.call('rm -rf %s' %tmp, shell = True)
        return out

    
    def parse(self, fn):
        """
        @param fn: source  file to parse
        @type fn: str

        @return: a dict
        """
        info = ProcheckInfo()
        
        f_handler = open(os.path.expanduser(fn))
        text = f_handler.read()
        
        inputFileName = re.compile('>>>-----.*?\n.*?\n\s*\|\s*(\S+)\s+')
        residues = re.compile('(\d+)\s*residues\s\|')
        ramachandranPlot = re.compile('Ramachandran\splot:\s*(\d+\.\d+)%\s*core\s*(\d+\.\d+)%\s*allow\s*(\d+\.\d+)%\s*gener\s*(\d+\.\d+)%\s*disall')
        labelledAll = re.compile('Ramachandrans:\s*(\d+)\s*.*?out\sof\s*(\d+)')
        labelledChi = re.compile('Chi1-chi2\splots:\s*(\d+)\s*.*?out\sof\s*(\d+)')
        badContacts = re.compile('Bad\scontacts:\s*(\d+)')
        gFactors = re.compile('G-factors\s*Dihedrals:\s*([0-9-+.]+)\s*Covalent:\s*([0-9-+.]+)\s*Overall:\s*([0-9-+.]+)')

        info['input_file']  = inputFileName.search(text).groups()[0]
        info['#residues']  = int(residues.search(text).groups()[0])
        info['rama_core'], info['rama_allow'], info['rama_gener'], info['rama_disall'] =\
                           ramachandranPlot.search(text).groups()
        info['g_dihedrals'], info['g_bond'], info['g_overall'] =\
                             gFactors.search(text).groups()

        f_handler.close()
        
        return info

if __name__ == "__main__":


    pp = ProcheckParser()
    pdbfile =  '~/data/whatif/2JZC.pdb'
    inf = pp.run(pdbfile)

    pdbfile =  '~/2kd7.pdb'
    inf2 = pp.run(pdbfile)