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
               myDataFile = self.config.getTestDataFile('some.file')
               self.assert...
        
       The "unit" decorator marks the test case as a collection of unit tests.
       All options are: csb.test.unit, csb.test.functional, csb.test.custom.
        
       If you need to add more initialization steps, you can override the
       default C{csb.test.Case.setUp}::
        
           def setUp(self):
               super(TestSomeClass, self).setUp()       # init the config
               # do something with self.config here...
                
       If you need to re-raise an exception by changing its signature::
       
           def testSomeMethod(self):
               try:
                   # do something that may crash
               except:
                   self.reRaise(addArgs=['Unhandled exception in data file ' + self.currentFile])
                   
       Writing custom (a.k.a. "data", "slow", "dynamic") tests is a little bit
       more work. Custom tests must be functions, not classes. Basically a
       custom test is a function, which builds a unittest.TestSuite instance 
       and then returns it when called without arguments.
           
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
"""

import os
import sys
import imp
import types
import cPickle
import hashlib
import tempfile
import unittest

from abc import ABCMeta, abstractproperty

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
        
        self.config = Config
        self.data = self.config.DATA
        self.temp = self.config.TEMP
        
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
        """
        file = self.getTestFile(fileName, subDir)
        return cPickle.load(open(file))
        
    def getTempStream(self):
        """
        Return a temporary file stream::
        
            with self.getTempStream() as tmp:
                tmp.write(something)
                tmp.flush()
                file_name = tmp.name
        
        @rtype: file stream
        """
        return tempfile.NamedTemporaryFile()

class Case(unittest.TestCase):
    """
    Base class, defining a CSB Test Case. Provides a default implementation
    of C{unittest.TestCase.setUp} which grabs a reference to a L{Config}.
    """
    
    def setUp(self):
        """
        Provide a reference to the CSB Test Config in the C{self.config} property.
        """   
        self.config = Config()
        assert hasattr(self.config, 'data'), 'The CSB Test Config must contain the data directory'
        assert self.config.data, 'The CSB Test Config must contain the data directory'
        
    def reRaise(self, addArgs=()):
        """
        Re-raise the last exception with its full traceback, but modify the
        argument list with C{addArgs}
        
        @param addArgs: additional arguments to append to the exception
        @type addArgs: tuple
        """
        ex = sys.exc_info()
        ex[1].args = list(ex[1].args) + list(addArgs)
        raise ex[0], ex[1], ex[2]  

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
        mod = imp.load_source(self._moduleHash(file), file)
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
        if not hasattr(namespaces, '__iter__'):
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
            directory = os.path.dirname(base)
        except ImportError:
            raise InvalidNamespaceError('Namespapce {0} is not importable'.format(namespace))
                
        for entry in os.walk(directory):
            
            for item in entry[2]:
                file = os.path.join(entry[0], item)
                if extension and item.endswith(extension):
                    suites.append(self.loadFromFile(file))
                
        return unittest.TestSuite(suites) 
    
    def _moduleHash(self, path):
        """
        Build a GUI used when importing a module with imp.
        
        @bug: If you don't use a unique name each time you import a module,
              python gets really confused. The results are unpredictable, but
              also silent - no exception, just corrupt program!
        """
        return hashlib.sha1(path).hexdigest()
    
    def _recurse(self, obj):
        """
        Extract test cases recursively from a test C{obj} container. 
        """   
        cases = []
        if isinstance(obj, unittest.TestSuite) or hasattr(obj, '__iter__'):
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
        labels = list(UnitTestBuilder().labels) + \
                 list(FunctionalTestBuilder().labels) + \
                 list(RegressionTestBuilder().labels)                 
        return labels

class UnitTestBuilder(AbstractTestBuilder):
    """
    Build a test suite of cases, marked as unit tests.
    For detailed documentation see L{AbstractTestBuilder}.    
    """   
    @property
    def labels(self):
        return ['__csbunittest__']
    
class FunctionalTestBuilder(AbstractTestBuilder):
    """
    Build a test suite of cases, marked as functional tests.
    For detailed documentation see L{AbstractTestBuilder}.    
    """ 
    @property
    def labels(self):
        return ['__csbfunctest__']    
    
class RegressionTestBuilder(AbstractTestBuilder):
    """
    Build a test suite of cases, marked as regression tests.
    For detailed documentation see L{AbstractTestBuilder}.    
    """ 
    @property
    def labels(self):
        return ['__csbregrtest__']        

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
        return ['__csbdatatest__']   
    
    def loadFromFile(self, file):
            
        mod = imp.load_source(self._moduleHash(file), file)
        suites = self._inspect(mod)
        
        return unittest.TestSuite(suites) 
                
    def loadTests(self, namespace):
        
        if namespace.endswith('.*'):
            return self.loadAllTests(namespace[:-2])
        elif namespace in ('__main__', '.'):
            main = __import__('__main__')
            return self.loadFromFile(main.__file__)
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
    if not isinstance(klass, (type, types.ClassType)):
        raise TypeError("Can't apply class decorator on {0}".format(type(klass)))
    
    klass.__csbunittest__ = True
    return klass

def functional(klass):
    """
    A class decorator, used to label functional test cases.
    
    @param klass: a C{unittest.TestCase} class type
    @type klass: type
    """
    if not isinstance(klass, (type, types.ClassType)):
        raise TypeError("Can't apply class decorator on {0}".format(type(klass))) 
       
    klass.__csbfunctest__ = True
    return klass

def regression(klass):
    """
    A class decorator, used to label regression test cases.
    
    @param klass: a C{unittest.TestCase} class type
    @type klass: type
    """
    if not isinstance(klass, (type, types.ClassType)):
        raise TypeError("Can't apply class decorator on {0}".format(type(klass))) 
       
    klass.__csbregrtest__ = True
    return klass
    
def custom(function):
    """
    A function decorator, used to mark functions which build custom (dynamic)
    test suites when called.
    
    @param function: a callable object, which returns a dynamically compiled
                     C{unittest.TestSuite}
    @type function: callable
    """
    if isinstance(function, (type, types.ClassType)):
        raise TypeError("Can't apply function decorator on a class")    
    elif not hasattr(function, '__call__'):
        raise TypeError("Can't apply function decorator on non-callable {0}".format(type(function))) 
       
    function.__csbdatatest__ = True
    return function

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
    """
    
    BUILDERS = {'unit': UnitTestBuilder, 'functional': FunctionalTestBuilder, 
                'custom': CustomTestBuilder, 'any': AnyTestBuilder, 
                'regression': RegressionTestBuilder}
    
    USAGE = r"""
CSB Test Runner Console. Usage:
 
     python {0.program} [-t type] [-v verbosity] namespace(s) 
 
Options:
          namespace(s)   A list of CSB test dotted namespaces, from which to
                         load tests. '__main__' and '.' are interpreted as the
                         current module. If a namespace ends with an asterisk
                         '.*', all sub-packages will be scanned as well.
                          
                         Examples:
                             csb.test.cases.bio.*
                             csb.test.cases.bio.io csb.test.cases.bio.utils
                             .
                             
      -t  type           Type of tests to load from each namespace. Possible
                         values are:
                             {0.builders}
                             
      -v  verbosity      Verbosity level passed to unittest.TextTestRunner.    
    """

    def __init__(self, namespace=('__main__',), builder=AnyTestBuilder, verbosity=1, argv=None):
        
        if not argv:
            argv = sys.argv
        
        if hasattr(namespace, '__iter__'):
            self.namespace = list(namespace)
        else:
            self.namespace = [namespace]            
        self.builder = builder
        self.builders = ', '.join(Console.BUILDERS)
        self.verbosity = verbosity
        self.program = os.path.basename(argv[0])
        
        self.parseArguments(argv[1:])
        self.run()
        
    def run(self):
        
        builder = self.builder()
        suite = builder.loadMultipleTests(self.namespace)

        runner = unittest.TextTestRunner(verbosity=self.verbosity)        
        runner.run(suite)
    
    def exit(self, message=None, code=0, usage=True):
        
        if message:
            print message
        if usage:
            print Console.USAGE.format(self)    
                
        sys.exit(code)        
        
    def parseArguments(self, argv):
        
        import getopt
        
        try:
            
            options, args = getopt.getopt(argv, 'h:t:v:', ['help', 'type=', 'verbosity='])
            
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
            
            if len(args) > 0:
                self.namespace = list(args)
                      
        except getopt.GetoptError as oe:
            self.exit(message='E: ' + str(oe), code=1)


if __name__ == '__main__':
       
    Console()