import sys
import operator
import csb.test as test
import csb.pyutils as utils 


@test.unit
class TestShell(test.Case):
    
    def setUp(self):
        
        super(TestShell, self).setUp()
        self.output = utils.Shell.run('echo TeST')
        
    def testSTDOUT(self):
        self.assertEquals(self.output.stdout.strip(), 'TeST')
        
    def testSTDERR(self):
        self.assertEquals(self.output.stderr, '')
        
    def testExitCode(self):
        self.assertEquals(self.output.code, 0)        

@test.unit
class TestDeepCopy(test.Case):
    
    def runTest(self):
        
        rec = sys.getrecursionlimit()
        obj = ['X']
        copy = utils.deepcopy(obj, recursion=(rec + 1))
        
        self.assertEquals(obj, copy)
        self.assertNotEquals(id(obj), id(copy))

@test.unit
class TestEnum(test.Case):
    
    def setUp(self):
    
        super(TestEnum, self).setUp()
        self.enum = utils.enum('A', 'B', C=66)
    
    def testConstructor(self):
        self.assertRaises(AttributeError, utils.enum, '3')
        self.assertRaises(ValueError, utils.enum, 'A', 'A')
        self.assertRaises(ValueError, utils.enum, A=1, B=1)                
        
    def testComparison(self):
        self.assertEqual(self.enum.A, 0)
        self.assertEqual(self.enum.C, 66)
        self.assertFalse(self.enum.C is 66)
        self.assertFalse(isinstance(self.enum.A, int))
        
    def testStr(self):
        self.assertEqual(str(self.enum.A), '0')
        self.assertEqual(int(self.enum.A), 0)        
        self.assertEqual(self.enum.A.value, 0)
        
    def testRepr(self):  
        self.assertEqual(repr(self.enum.A), 'A')        
        self.assertEqual(self.enum.A.name, 'A')

    def testMembers(self):
        result = utils.Enum.members(self.enum)
        members = [self.enum.A, self.enum.B, self.enum.C]
        self.assertEquals(set(result), set(members))

    def testNames(self):
        result = utils.Enum.names(self.enum)
        names = map(repr, [self.enum.A, self.enum.B, self.enum.C])
        names2 = map(operator.attrgetter('name'), [self.enum.A, self.enum.B, self.enum.C])        
        self.assertEquals(set(result), set(names))
        self.assertEquals(set(result), set(names2))        
        
    def testValues(self):
        result = utils.Enum.values(self.enum)
        values = map(int, [self.enum.A, self.enum.B, self.enum.C])
        values2 = map(operator.attrgetter('value'), [self.enum.A, self.enum.B, self.enum.C])        
        self.assertEquals(set(result), set(values))
        self.assertEquals(set(result), set(values2))

    def testParseValue(self):
        item = utils.Enum.parse(self.enum, 66)
        self.assertTrue(item is self.enum.C)        
        self.assertRaises(utils.EnumValueError, utils.Enum.parse, self.enum, 111)
        self.assertRaises(utils.EnumValueError, utils.Enum.parse, self.enum, '0') 
                
    def testParseName(self):
        item = utils.Enum.parsename(self.enum, 'A')
        self.assertTrue(item is self.enum.A)
        self.assertRaises(utils.EnumMemberError, utils.Enum.parsename, self.enum, 'XXX')

    def testIsMember(self):
        self.assertTrue(utils.Enum.ismember(self.enum.A, self.enum))
        
@test.unit
class TestDictionaryContainer(test.Case):
    
    def setUp(self):
        
        super(TestDictionaryContainer, self).setUp()
        
        self.dict = utils.OrderedDict({'A': 1, 'B': 2})
        self.keys = ('A', 'B', 'C', 'D', 'Z')
        self.new = utils.DictionaryContainer
        self.test = utils.DictionaryContainer(items=self.dict, restrict=self.keys)
            
    def testConstructor(self):
        new = utils.DictionaryContainer(items=self.dict, restrict=self.keys)
        self.assertEqual(dict(new), dict(self.dict))
        self.assertEqual(list(new), list(self.dict))    # True if the dictionary is ordered        
        self.assertEqual(new.length, len(self.dict))        
        self.assertRaises(utils.InvalidKeyError, self.new, items={'X': 1}, restrict=self.keys)        
    
    def testAppend(self):
        self.test.append('C', 1)
        self.assertTrue('C' in self.test)
        self.assertRaises(utils.DuplicateKeyError, self.test.append, key='C', item=1)                            
        self.assertRaises(utils.InvalidKeyError, self.test.append, key='X', item=1)        
    
    def testRemove(self):
        self.assertTrue('A' in self.test)        
        self.test._remove('A')
        self.assertFalse('A' in self.test)
        
    def testGetitem(self):
        self.assertEqual(self.test['B'], self.dict['B'])     
        self.assertRaises(utils.ItemNotFoundError, lambda k: self.test[k], 66)
        
    def testSet(self):
        new = utils.DictionaryContainer(items=self.dict, restrict=self.keys)
        new._set({'Z': 6})
        self.assertTrue('Z' in new)
        self.assertFalse('A' in new)
        
    def testUpdate(self):
        new = utils.DictionaryContainer(items=self.dict, restrict=self.keys)

        new._update({'A': 7})
        self.assertTrue('A' in new)
        self.assertEquals(new['A'], 7)
        
        self.assertRaises(utils.ItemNotFoundError, new._update, {'Z': 0})

@test.unit
class TestCollectionContainer(test.Case):

    def setUp(self):
        
        super(TestCollectionContainer, self).setUp()
        
        self.items = [11, 22, 33]
        self.start = 5
        self.new = utils.CollectionContainer
        self.test = utils.CollectionContainer(items=self.items, type=int, start_index=self.start)
            
    def testConstructor(self):
        new = utils.CollectionContainer(items=self.items, type=int, start_index=self.start)
        self.assertEqual(list(new), list(self.items))
        self.assertEqual(new.length, len(self.items))        
        self.assertRaises(TypeError, self.new, items=['S', 1.2], type=int)

    def testGetitem(self):
        self.assertEqual(self.test[self.start], self.items[0])
        self.assertEqual(self.test[self.test.start_index], self.items[0])        
        self.assertEqual(self.test[self.test.last_index], self.items[-1])
        self.assertEqual(self.test[-1], self.items[-1])
        self.assertEqual(self.test[-1 : -2], self.items[-1 : -2])                            
        
        def get(i):
            return self.test[i]
         
        self.assertRaises(utils.CollectionIndexError, get, self.start + len(self.items))  # i = end + 1
        if self.start > 0:
            self.assertRaises(utils.CollectionIndexError, get, self.start - 1)            # i = start - 1, i >= 0
                
    def testIndices(self):
        new = self.new(items=self.items, type=int, start_index=self.start)
        self.assertEqual(new.start_index, self.start)                
        self.assertEqual(new.last_index, self.start + len(self.items) - 1)    
        self.assertEqual(new.length, len(self.items)) 
    
    def testAppend(self):
        rank = self.test.append(44)
        self.assertTrue(44 in self.test)
        self.assertEqual(rank, self.test.last_index)
        self.assertRaises(TypeError, self.test.append, item='S')                                    

    def testUpdate(self):
        new = self.new(items=self.items, type=int, start_index=self.start)

        new._update([98, 99])
        self.assertTrue(98 in new)
        self.assertEquals(new.length, 2)
        
        self.assertRaises(TypeError, new._update, ['S'])

@test.unit
class TestAbstractContainer(test.Case):
    
    def setUp(self):
        
        super(TestAbstractContainer, self).setUp()

        dictitems = {'A': 1, 'B': 2}
        self.items = dictitems
        
        listitems = [11, 22]
        start = 5
        self.listitems = listitems
        self.start = start
        
        class DummyDict(utils.AbstractContainer):
            @property
            def _children(self):
                return utils.DictionaryContainer(dictitems)
            
        class DummyList(utils.AbstractContainer):
            @property
            def _children(self):
                return utils.CollectionContainer(listitems, start_index=start)            
        
        self.dict = DummyDict()
        self.list = DummyList()
        
    def testGetitem(self):
        self.assertEqual(self.dict['A'], 1)
        self.assertRaises(utils.ItemNotFoundError, lambda k: self.dict[k], 'X')

        self.assertEqual(self.list[self.start], self.listitems[0])
        if self.start > 0:
            self.assertRaises(utils.CollectionIndexError, lambda i: self.list[i], 0)
            
    def testIterator(self):
        self.assertEqual(list(self.items), list(self.dict))
        self.assertEqual(list(self.listitems), list(self.list))        
        
@test.unit
class TestAbstractNIContainer(test.Case):
    
    def setUp(self):
        
        super(TestAbstractNIContainer, self).setUp()

        items = list(set([11, 22, 33]))
        start = 1

        self.items = items
        self.start = start
        
        class Dummy(utils.AbstractNIContainer):
            @property
            def _children(self):
                return utils.CollectionContainer(items, start_index=start)         
        
        self.test = Dummy()     
        
    def testGetitem(self):
        assert self.start > 0
        
        self.assertEqual(self.test[0], self.items[0])
        self.assertEqual(self.test[1:2], self.items[1:2])         
        self.assertEqual(self.test[0], self.test._children[self.start])
        self.assertNotEqual(self.test[1], self.test._children[1])        
                
        self.assertRaises(IndexError, lambda i: self.test[i], 9999999)
    
    def testIterator(self):
        self.assertEqual(list(self.items), list(self.test))
            
        
if __name__ == '__main__':
    
    test.Console()        