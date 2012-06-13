"""
This is the top level package of the CSB's testing framework. It is divided
into several major components:

    - test cases, located under csb.test.cases
    - test data, in /csb/test/data (not a package)
    - test console, in /csb/test/app.py

This module, csb.test, contains all the glue-code functions, classes and 
decorators you need in order to write tests for CSB.    

    1. Configuration and Tree
    
       csb.test.Config is the common config shared between CSB tests. Each
       config instance contains properties like:
            
            - data: the data folder, automatically discovered in 
              csb.test.Config.DATA at module import time
            - temp: a default temp folder, which tests may use
        
       Each config instance has a standard method for test file retrieval,
       called C{config.getTestFile}.
        
       All test data files should be placed in the C{data} folder. All test
       modules must be placed in the root package: C{csb.test.cases}. There is
       a strict naming convention for test modules: the name of a test module
       should be the same as the name of the CSB API package it tests. For 
       example, if you write a test module for C{csb/bio/io/__init__.py}, the
       test module must be C{csb/test/cases/bio/io/__init__.py}. Therefore, 
       C{csb.test.cases} is the "root" package of all test packages.
    
    2. Writing Tests
    
       Writing a test is easy. All you need is to import csb.test and then
       create your own test cases, derived from csb.test.Case::
       
           @csb.test.unit
           class TestSomeClass(csb.test.Case):
               # test methods here...
       
       In this way your test case instance is automatically equipped with a 
       reference to the test config, so your test method can be::
       
           def testSomeMethod(self):
               myDataFile = self.config.getTestFile('some.file')
               self.assert...
        
       The "unit" decorator marks the test case as a collection of unit tests.
       All options are: csb.test.unit, csb.test.functional, csb.test.custom,
       and csb.test.regression.
        
       If you need to add more initialization steps, you can override the
       default C{csb.test.Case.setUp}::
        
           def setUp(self):
               super(TestSomeClass, self).setUp()       # init the config
               # do something with self.config here...
                   
       Writing custom (a.k.a. "data", "slow", "dynamic") tests is a little bit
       more work. Custom tests must be functions, not classes. Basically a
       custom test is a function, which builds a unittest.TestSuite instance 
       and then returns it when called without arguments.
       
       Regression tests are closely related with reported bugs. Therefore, 
       the best practice is to mark each test method with its relevant bug ID::
       
           @csb.test.regression
           class SomeClassRegressions(csb.test.Case)
               
               def testSomeFeature(self)
               \"""
               @see: [CSB 000XXXX] 
               \"""
               # regression test body...
           
    3. Style Guide:
    
       - name test case packages as already described
       - group tests in csb.test.Case-s and name them properly
       - prefix test methods with "test", like "testParser" - very important
       - use camelCase for methods and variables. This applies to all the
         code under csb.test (including test) and does not apply to the rest
         of the library!
       - for functional tests, you can create only one test method: runTest
       - for unit tests, you can make test names atomic, for example: 
         "testParseFile" - a unit test for some method called "parse_file"
       - use csb.test decorators to mark tests as unit, functional or custom
       - in each test module put::
       
           if __name__ == '__main__':
               csb.test.Console()
    
    4. Test Execution
    
       The test execution is handled by C{test builders} and a test runner
       C{app}. Test builders are subclasses of L{AbstractTestBuilder}. 
       We have one test builder specialized to load a specific test type: 
       unit, functional, custom. L{AnyTestBuilder} will scan for either unit
       or functional tests.
    
       The test runner app is C{csb/test/app.py} which is simply an instance
       of L{csb.test.Console}. The app has two major arguments: 
    
           - test type, which controls which TestBuilder will handle the test
             module scan (e.g.: "any" triggers L{AnyTestBuilder}, "unit" - 
             L{UnitTestBuilder} and so on) 
           - test namespaces - a list of "dotted" test cases, e.g.::
    
                csb.test.cases.bio.io.*   # io and sub-packages
                csb.test.cases.bio.utils  # only utils
                __main__                  # current module
    
           Run the app with '-h' for full documentation.
    
       In addition to running the app from the command line, you can run it
       also programmatically by instantiating L{csb.test.Console}. You can
       construct a test console object by supplying target test namespace(s)
       and a test builder class in the constructor.
    
       Test builder classes inherit the following test discovery methods:
    
           - C{loadTests} - load tests from a test namespace. Wildcard
             namespaces are handled by C{loadAllTests}
           - C{loadAllTests} - load tests from the given namespace, and
             from all sub-packages (recursive)
           - C{loadFromFile} - load tests from an absolute file name
           - C{loadMultipleTests} - calls C{loadTests} for a list of 
             namespaces and combines all loaded tests in a single suite
    
    5. Commit Policies
    
       Follow these guidelines when making changes to the repository:
    
           - No Bugs in the Repository: after fixing a bug or implementing a new
             feature, make sure at least the default test set passes by running
             the test console without any arguments. This is equivalent to:
             app.py -t any "csb.test.cases.*". (If no test case from this set covers
             the affected code, create a test case first, as described in the other
             policies)
    
           - No Recurrent Issues: when a bug is observed, first write a regression
             test with a proper "@see: BugID" tag in the docstring. Run the test
             to make sure it fails. After fixing the bug, run the test again before
             you commit, as required by the "No Bugs in the Repository" policy
             
           - Test New Features: there should be a test case for every new feature
             we implement. One possible approach is to write a test case first and
             make sure it fails; when the new feature is ready, run the test again
             to make sure it passes

@warning: for compatibility reasons do NOT import and use the unittest module
          directly. Always import unittest from csb.test, which is guaranteed
          to be python 2.7+ compatible. The standard unittest under python 2.6
          is missing some features, that's why csb.test will take care of
          replacing it with unittest2 instead. 
"""
from __future__ import print_function

import os
import sys
import imp
import types
import time
import getopt
import tempfile
import traceback

import csb.io
import csb.core

try:
    from unittest import skip, skipIf
    import unittest
except ImportError:
    import unittest2 as unittest

from abc import ABCMeta, abstractproperty


class Attributes(object):
    
    UNIT       = '__CSBUnitTest__'
    CUSTOM     = '__CSBCustomTest__'    
    FUNCTIONAL = '__CSBFunctionalTest__'
    REGRESSION = '__CSBRegressionTest__'    

class Config(object):
    """
    General CSB Test Config. Config instances contain the following properties:
    
        - data - path to the CSB Test Data directory. Default is L{Config.DATA}
        - temp - path to the system's temp directory. Default is L{Config.TEMP}        
        - config - the L{Config} class
    """
    
    DATA = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')
    """
    @cvar: path to the default test data directory: <install dir>/csb/test/data 
    """
    TEMP = os.path.abspath(tempfile.gettempdir())
    """
    @cvar: path to the default system's temp directory
    """
    
    def __init__(self):
        
        self.__config = Config
        self.__data = self.config.DATA
        self.__temp = self.config.TEMP

    @staticmethod
    def setDefaultDataRoot(path):
        """
        Override the default L{Config.DATA} with a new data root directory.
        
        @param path: full directory path
        @type path: str
        """
        if not os.path.isdir(path):
            raise IOError('Path not found: {0}'.format(path))
        
        Config.DATA = os.path.abspath(path)
        
    @property
    def config(self):
        return self.__config
    
    @property
    def data(self):
        return self.__data
    
    @property
    def temp(self):
        return self.__temp
        
    def getTestFile(self, fileName, subDir=''):
        """
        Search for C{fileName} in the L{Config.DATA} directory.
        
        @param fileName: the name of a test file to retrieve
        @type fileName: str
        @param subDir: scan a sub-directory of L{Config.DATA}
        @type subDir: str        
        
        @return: full path to C{fileName}
        @rtype: str
        
        @raise IOError: if no such file is found
        """     
        file = os.path.join(self.data, subDir, fileName)
        if not os.path.isfile(file):
            raise IOError('Test file not found: {0}'.format(file))
        return file          
    
    def getPickle(self, fileName, subDir=''):
        """
        Same as C{self.getTestFile}, but try to unpickle the data in the file.

        @param fileName: the name of a test file to retrieve
        @type fileName: str
        @param subDir: scan a sub-directory of L{Config.DATA}
        @type subDir: str           
        """
        file = self.getTestFile(fileName, subDir)
        return csb.io.Pickle.load(open(file, 'rb'))
    
    def getContent(self, fileName, subDir=''):
        """
        Same as C{self.getTestFile}, but also read and return the contents of
        the file.
        
        @param fileName: the name of a test file to retrieve
        @type fileName: str
        @param subDir: scan a sub-directory of L{Config.DATA}
        @type subDir: str           
        """
        with open(self.getTestFile(fileName, subDir)) as f:
            return f.read()
        
    def getTempStream(self, mode='t'):
        """
        Return a temporary file stream::
        
            with self.getTempStream() as tmp:
                tmp.write(something)
                tmp.flush()
                file_name = tmp.name
        
        @param mode: file open mode (text, binary), default=t
        @type mode: str
        @rtype: file stream
        """
        return csb.io.TempFile(mode=mode)
    
    def ensureDataConsistency(self):
        """
        Try to deserialize some pickled data files. Call L{Config.updateDataFiles}
        if the pickles appeared incompatible with the current interpreter.
        """
        try:
            self.getPickle('1nz9.model1.pickle')
        except:
            self.updateDataFiles()
        
    def updateDataFiles(self):
        """
        Refresh the pickled structures in csb/test/data. This might be needed when
        the internal representation of some classes has changed.
        """
        from csb.io import Pickle
        from csb.bio.io.wwpdb import get
        from csb.bio.structure import Ensemble, ChemElements
    
        model1 = get('1nz9', model=1)
        model2 = get('1nz9', model=2)
        
        ensemble = Ensemble()
        ensemble.models.append(model1)
        ensemble.models.append(model2)
        Pickle.dump(ensemble, open(os.path.join(self.data, '1nz9.full.pickle'), 'wb'))
        
        mse = model1.chains['A'].find(164)
        mse._pdb_name = 'MSE'
        mse.atoms['SD']._element = ChemElements.Se
        mse.atoms['SD']._full_name = 'SE  '
        Pickle.dump(model1, open(os.path.join(self.data, '1nz9.model1.pickle'), 'wb'))    

class Case(unittest.TestCase):
    """
    Base class, defining a CSB Test Case. Provides a default implementation
    of C{unittest.TestCase.setUp} which grabs a reference to a L{Config}.
    """
    @property
    def config(self):
        return self.__config
    
    def setUp(self):
        """
        Provide a reference to the CSB Test Config in the C{self.config} property.
        """   
        self.__config = Config()
        assert hasattr(self.config, 'data'), 'The CSB Test Config must contain the data directory'
        assert self.config.data, 'The CSB Test Config must contain the data directory'
        
    def reRaise(self, addArgs=()):
        """
        Re-raise the last exception with its full traceback, but modify the
        argument list with C{addArgs} and the original stack trace.
        
        @param addArgs: additional arguments to append to the exception
        @type addArgs: tuple
        """
        klass, ex, _tb = sys.exc_info()
        ex.args = list(ex.args) + list(addArgs) + [''.join(traceback.format_exc())]
        
        raise klass(ex.args)
    
    def assertFasterThan(self, duration, callable, *args, **kargs):
        """
        Fail if it took more than C{duration} seconds to invoke C{callable}.
        
        @param duration: maximum amount of seconds allowed 
        @type duration: float 
        """
        
        start = time.time()
        callable(*args, **kargs)
        execution = time.time() - start
        
        if execution > duration:
            self.fail('{0}s is slower than {1}s)'.format(execution, duration))

    def assertWithinDelta(self, value, expected, delta=1e-1):
        """
        Fail if the difference is larger than delta
        
        @param value: input value
        @type value: float

        @param expected: expected value
        @type expected: float

        @param delta: allowed deviation
        @type delta: float
        """
        
        if abs(value - expected) > delta:
            self.fail('|{0} - {1}| > {2})'.format(value, expected, delta))
            
    @classmethod
    def execute(cls):
        """
        Run this test case.
        """
        suite = unittest.TestLoader().loadTestsFromTestCase(cls)
        runner = unittest.TextTestRunner()
                
        return runner.run(suite)            

class InvalidNamespaceError(NameError, ImportError):
    pass
    
class AbstractTestBuilder(object):
    """
    This is a base class, defining a test loader which exposes the C{loadTests}
    method.
    
    Subclasses must override the C{labels} abstract property, which controls 
    what kind of test cases are loaded by the test builder.
    """
    
    __metaclass__ = ABCMeta
    
    @abstractproperty
    def labels(self):
        pass
    
    def loadFromFile(self, file):
        """
        Load L{csb.test.Case}s from a module file.
        
        @param file: test module file name
        @type file: str
        
        @return: a C{unittest.TestSuite} ready for the test runner
        @rtype: C{unittest.TestSuite}         
        """         
        mod = self._loadSource(file)
        suite = unittest.TestLoader().loadTestsFromModule(mod)        
        return unittest.TestSuite(self._filter(suite)) 
                
    def loadTests(self, namespace):
        """
        Load L{csb.test.Case}s from the given CSB C{namespace}. If the namespace
        ends with a wildcard, tests from sub-packages will be loaded as well.
        If the namespace is '__main__' or '.', tests are loaded from __main__. 
        
        @param namespace: test module namespace, e.g. 'csb.test.cases.bio' will
                          load tests from '/csb/test/cases/bio/__init__.py'
        @type namespace: str
        
        @return: a C{unittest.TestSuite} ready for the test runner
        @rtype: C{unittest.TestSuite} 
        """
        if namespace.strip() == '.*':
            namespace = '__main__.*'
        elif namespace.strip() == '.':
            namespace = '__main__'
        
        if namespace.endswith('.*'):
            return self.loadAllTests(namespace[:-2])
        else:            
            loader = unittest.TestLoader()
            tests = loader.loadTestsFromName(namespace)                   
            return unittest.TestSuite(self._filter(tests))
    
    def loadMultipleTests(self, namespaces):
        """
        Load L{csb.test.Case}s from a list of given CSB C{namespaces}.
        
        @param namespaces: a list of test module namespaces, e.g. 
                           ('csb.test.cases.bio', 'csb.test.cases.bio.io') will
                           load tests from '/csb/test/cases/bio.py' and 
                           '/csb/test/cases/bio/io.py'
        @type namespaces: tuple of str
        
        @return: a C{unittest.TestSuite} ready for the test runner
        @rtype: C{unittest.TestSuite} 
        """
        if not csb.core.iterable(namespaces):
            raise TypeError(namespaces)
        
        return unittest.TestSuite(self.loadTests(n) for n in namespaces)
    
    def loadAllTests(self, namespace, extension='.py'):
        """
        Load L{csb.test.Case}s recursively from the given CSB C{namespace} and
        all of its sub-packages. Same as::
        
            builder.loadTests('namespace.*')
        
        @param namespace: test module namespace, e.g. 'csb.test.cases.bio' will
                          load tests from /csb/test/cases/bio/*'
        @type namespace: str
        
        @return: a C{unittest.TestSuite} ready for the test runner
        @rtype: C{unittest.TestSuite} 
        """        
        suites = []
        
        try:
            base = __import__(namespace, level=0, fromlist=['']).__file__
        except ImportError:
            raise InvalidNamespaceError('Namespapce {0} is not importable'.format(namespace))
        
        if os.path.splitext(os.path.basename(base))[0] != '__init__':
            suites.append(self.loadTests(namespace))
        
        else:
            
            for entry in os.walk(os.path.dirname(base)):
                
                for item in entry[2]:
                    file = os.path.join(entry[0], item)
                    if extension and item.endswith(extension):
                        suites.append(self.loadFromFile(file))
                
        return unittest.TestSuite(suites) 
    
    def _loadSource(self, path):
        """
        Import and return the Python module identified by C{path}.
        
        @note: Module objects behave as singletons. If you import two different
               modules and give them the same name in imp.load_source(mn), this
               counts for a redefinition of the module originally named mn, which
               is basically the same as reload(mn). Therefore, you need to ensure
               that for every call to imp.load_source(mn, src.py) the mn parameter
               is a string that uniquely identifies the source file src.py.
        """
        name = os.path.splitext(os.path.abspath(path))[0]
        name = name.replace('.', '-').rstrip('__init__').strip(os.path.sep)
        
        return imp.load_source(name, path)        
    
    def _recurse(self, obj):
        """
        Extract test cases recursively from a test C{obj} container. 
        """   
        cases = []
        if isinstance(obj, unittest.TestSuite) or csb.core.iterable(obj):
            for item in obj:
                cases.extend(self._recurse(item))
        else:
            cases.append(obj)
        return cases        
                        
    def _filter(self, tests):
        """
        Filter a list of objects using C{self.labels}.
        """
        filtered = []
        
        for test in self._recurse(tests):
            for label in self.labels:
                if hasattr(test, label) and getattr(test, label) is True:
                    filtered.append(test)
        
        return filtered  
                    
class AnyTestBuilder(AbstractTestBuilder):
    """
    Build a test suite of cases, marked as either unit, functional or regression
    tests. For detailed documentation see L{AbstractTestBuilder}.
    """
    @property
    def labels(self):
        return [Attributes.UNIT, Attributes.FUNCTIONAL, Attributes.REGRESSION]             

class UnitTestBuilder(AbstractTestBuilder):
    """
    Build a test suite of cases, marked as unit tests.
    For detailed documentation see L{AbstractTestBuilder}.    
    """   
    @property
    def labels(self):
        return [Attributes.UNIT]
    
class FunctionalTestBuilder(AbstractTestBuilder):
    """
    Build a test suite of cases, marked as functional tests.
    For detailed documentation see L{AbstractTestBuilder}.    
    """ 
    @property
    def labels(self):
        return [Attributes.FUNCTIONAL]    
    
class RegressionTestBuilder(AbstractTestBuilder):
    """
    Build a test suite of cases, marked as regression tests.
    For detailed documentation see L{AbstractTestBuilder}.    
    """ 
    @property
    def labels(self):
        return [Attributes.REGRESSION]        

class CustomTestBuilder(AbstractTestBuilder):
    """
    Build a test suite of cases, marked as custom tests. CustomTestBuilder will
    search for functions, marked with the 'custom' test decorator, which return
    a dynamically built C{unittest.TestSuite} object when called without 
    parameters. This is convenient when doing data-related tests, e.g. 
    instantiating a single type of a test case many times iteratively, for 
    each entry in a database. 
    
    For detailed documentation see L{AbstractTestBuilder}.    
    """
    @property
    def labels(self):
        return [Attributes.CUSTOM]   
    
    def loadFromFile(self, file):
            
        mod = self._loadSource(file)
        suites = self._inspect(mod)
        
        return unittest.TestSuite(suites) 
                
    def loadTests(self, namespace):

        if namespace.strip() == '.*':
            namespace = '__main__.*'
        elif namespace.strip() == '.':
            namespace = '__main__'
                    
        if namespace.endswith('.*'):
            return self.loadAllTests(namespace[:-2])
        else:
            try:
                mod = __import__(namespace, fromlist=[''])
            except ImportError:
                raise InvalidNamespaceError('Namespace {0} is not importable'.format(namespace))
            suites = self._inspect(mod)                  
            return unittest.TestSuite(suites)    
    
    def _inspect(self, module):
        
        objects = map(lambda n: getattr(module, n), dir(module))
        return self._filter(objects)        
    
    def _filter(self, factories):
        """
        Filter a list of objects using C{self.labels}.
        """
        filtered = []
        
        for obj in factories:
            for label in self.labels:
                if hasattr(obj, label) and getattr(obj, label) is True:
                    suite = obj()
                    if not isinstance(suite, unittest.TestSuite):
                        raise ValueError('Custom test function {0} must return a '
                                         'unittest.TestSuite, not {1}'.format(obj.__name__, type(suite)))
                    filtered.append(suite)
        
        return filtered           

def unit(klass):
    """
    A class decorator, used to label unit test cases.
    
    @param klass: a C{unittest.TestCase} class type
    @type klass: type
    """
    if not isinstance(klass, type):
        raise TypeError("Can't apply class decorator on {0}".format(type(klass)))
    
    setattr(klass, Attributes.UNIT, True)
    return klass

def functional(klass):
    """
    A class decorator, used to label functional test cases.
    
    @param klass: a C{unittest.TestCase} class type
    @type klass: type
    """
    if not isinstance(klass, type):
        raise TypeError("Can't apply class decorator on {0}".format(type(klass))) 
       
    setattr(klass, Attributes.FUNCTIONAL, True)
    return klass

def regression(klass):
    """
    A class decorator, used to label regression test cases.
    
    @param klass: a C{unittest.TestCase} class type
    @type klass: type
    """
    if not isinstance(klass, type):
        raise TypeError("Can't apply class decorator on {0}".format(type(klass))) 
       
    setattr(klass, Attributes.REGRESSION, True)
    return klass
    
def custom(function):
    """
    A function decorator, used to mark functions which build custom (dynamic)
    test suites when called.
    
    @param function: a callable object, which returns a dynamically compiled
                     C{unittest.TestSuite}
    @type function: callable
    """
    if isinstance(function, type):
        raise TypeError("Can't apply function decorator on a class")    
    elif not hasattr(function, '__call__'):
        raise TypeError("Can't apply function decorator on non-callable {0}".format(type(function))) 
       
    setattr(function, Attributes.CUSTOM, True)
    return function

def skip(reason, condition=None):
    """
    Mark a test case or method for skipping.
    
    @param reason: message
    @type reason: str
    @param condition: skip only if the specified condition is True
    @type condition: bool/expression
    """
    if isinstance(reason, types.FunctionType):
        raise TypeError('skip: no reason specified')
        
    if condition is None:
        return unittest.skip(reason)
    else:
        return unittest.skipIf(condition, reason)

class Console(object):
    """
    Build and run all tests of the specified namespace and kind.
    
    @param namespace: a dotted name, which specifies the test module 
                      (see L{csb.test.AbstractTestBuilder.loadTests})
    @type namespace: str
    @param builder: test builder to use
    @type builder: any L{csb.test.AbstractTestBuilder} subclass
    @param verbosity: verbosity level for C{unittest.TestRunner}
    @type verbosity: int
    @param update: if True, refresh all pickles in csb/test/data
    @type update: bool
    """
    
    BUILDERS = {'unit': UnitTestBuilder, 'functional': FunctionalTestBuilder, 
                'custom': CustomTestBuilder, 'any': AnyTestBuilder, 
                'regression': RegressionTestBuilder}
    
    USAGE = r"""
CSB Test Runner Console. Usage:
 
     python {0.program} [-u] [-t type] [-v verbosity] namespace(s) 
 
Options:
      namespace(s)       A list of CSB test dotted namespaces, from which to
                         load tests. '__main__' and '.' are interpreted as the
                         current module. If a namespace ends with an asterisk
                         '.*', all sub-packages will be scanned as well.
                          
                         Examples:
                             "csb.test.cases.bio.*"
                             "csb.test.cases.bio.io" "csb.test.cases.bio.utils"
                             "."
                             
      -t  type           Type of tests to load from each namespace. Possible
                         values are:
                             {0.builders}
                             
      -v  verbosity      Verbosity level passed to unittest.TextTestRunner.
      
      -u  update-files   Force update of the test pickles in csb/test/data.
    """

    def __init__(self, namespace=('__main__',), builder=AnyTestBuilder, verbosity=1,
                 update=False, argv=None):
        
        if not argv:
            argv = sys.argv
        
        self._namespace = None            
        self._builder = None
        self._verbosity = 1
        self._update = False
        self._program = os.path.basename(argv[0])
        
        self.namespace = namespace
        self.builder = builder
        self.verbosity = verbosity
        self.update = update
        
        self.parseArguments(argv[1:])
        self.run()
        
    @property
    def namespace(self):
        return self._namespace
    @namespace.setter
    def namespace(self, value):    
        if csb.core.iterable(value):
            self._namespace = list(value)
        else:
            self._namespace = [value]
            
    @property
    def builder(self):
        return self._builder
    @builder.setter
    def builder(self, value):
        self._builder = value
    
    @property
    def verbosity(self):
        return self._verbosity
    @verbosity.setter
    def verbosity(self, value):
        self._verbosity = value    
            
    @property
    def builders(self):
        return ', '.join(Console.BUILDERS)
    
    @property
    def program(self):
        return self._program
    
    @property
    def update(self):
        return self._update
    @update.setter
    def update(self, value):
        self._update = bool(value)
                    
    def run(self):
        
        if self.update:
            Config().updateDataFiles()
        else:
            Config().ensureDataConsistency()
        
        builder = self.builder()
        suite = builder.loadMultipleTests(self.namespace)

        runner = unittest.TextTestRunner(verbosity=self.verbosity)        
        runner.run(suite)
    
    def exit(self, message=None, code=0, usage=True):
        
        if message:
            print(message)
        if usage:
            print(Console.USAGE.format(self))    
                
        sys.exit(code)        
        
    def parseArguments(self, argv):
        
        try:
            
            options, args = getopt.getopt(argv, 'hut:v:', ['help', 'update-files', 'type=', 'verbosity='])
            
            for option, value in options:
                if option in('-h', '--help'):
                    self.exit(message=None, code=0)
                if option in('-t', '--type'):
                    try:
                        self.builder = Console.BUILDERS[value]
                    except KeyError:
                        self.exit(message='E: Invalid test type "{0}".'.format(value), code=2)                  
                if option in('-v', '--verbosity'):
                    try:
                        self.verbosity = int(value)
                    except ValueError:
                        self.exit(message='E: Verbosity must be an integer.', code=3)
                if option in('-u', '--update-files'):
                    self.update = True
                                
            if len(args) > 0:
                self.namespace = list(args)
                      
        except getopt.GetoptError as oe:
            self.exit(message='E: ' + str(oe), code=1)


if __name__ == '__main__':
       
    Console()
