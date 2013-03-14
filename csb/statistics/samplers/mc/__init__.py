"""
Abstract Monte Carlo samplers.
"""

import numpy.random

import csb.numeric
import csb.core

from abc import ABCMeta, abstractmethod, abstractproperty
from csb.statistics.samplers import AbstractSampler, AbstractState, State, EnsembleState

class AbstractMC(AbstractSampler):
    """
    Abstract Monte Carlo sampler class. Subclasses implement various
    Monte carlo equilibrium sampling schemes.
    
    @param state: Initial state
    @type state: L{AbstractState}
    """
    
    __metaclass__ = ABCMeta
    
    def __init__(self, state):
        
        self._state = None
        self.state = state
         
    def _checkstate(self, state):
        
        if not isinstance(state, AbstractState):
            raise TypeError(state)
    
    @abstractproperty
    def energy(self):
        """
        Energy of the current state.
        """
        pass

    @property
    def state(self):
        """
        Current state.
        """
        return self._state
    @state.setter
    def state(self, value):
        self._checkstate(value)
        self._state = value

    @abstractmethod
    def sample(self):
        """
        Draw a sample.
        @rtype: L{AbstractState}
        """
        pass

class AbstractPropagationResult(object):
    """
    Abstract class providing the interface for the result
    of a deterministic or stochastic propagation of a state.
    """
    
    __metaclass__ = ABCMeta 
    
    @abstractproperty
    def initial(self):
        """
        Initial state
        """
        pass
    
    @abstractproperty
    def final(self):
        """
        Final state
        """
        pass
    
    @abstractproperty
    def heat(self):
        """
        Heat produced during propagation
        @rtype: float
        """        
        pass    

class PropagationResult(AbstractPropagationResult):
    """
    Describes the result of a deterministic or stochastic
    propagation of a state.

    @param initial: Initial state from which the
                    propagation started
    @type initial: L{State}

    @param final: Final state in which the propagation
                  resulted
    @type final: L{State}

    @param heat: Heat produced during propagation
    @type heat: float
    """
    
    
    def __init__(self, initial, final, heat=0.0):
        
        if not isinstance(initial, AbstractState):
            raise TypeError(initial)
        
        if not isinstance(final, AbstractState):
            raise TypeError(final)        
        
        self._initial = initial
        self._final = final
        self._heat = None
        
        self.heat = heat
        
    @property
    def initial(self):
        return self._initial
    
    @property
    def final(self):
        return self._final
    
    @property
    def heat(self):
        return self._heat
    @heat.setter
    def heat(self, value):
        self._heat = float(value)

class Trajectory(csb.core.CollectionContainer, AbstractPropagationResult):
    """
    Ordered collection of states, representing a phase-space trajectory.

    @param items: list of states defining a phase-space trajectory
    @type items: list of L{AbstractState}
    @param heat: heat produced during the trajectory
    @type heat: float
    @param work: work produced during the trajectory
    @type work: float
    """
    
    def __init__(self, items, heat=0.0, work=0.0):
        
        super(Trajectory, self).__init__(items, type=AbstractState)
        
        self._heat = heat    
        self._work = work
    
    @property
    def initial(self):
        return self[0]
    
    @property
    def final(self):
        return self[self.last_index]
    
    @property
    def heat(self):
        return self._heat
    @heat.setter
    def heat(self, value):
        self._heat = float(value)

    @property
    def work(self):
        return self._work
    @work.setter
    def work(self, value):
        self._work = float(value)

class TrajectoryBuilder(object):
    """
    Allows to  build a Trajectory object step by step.

    @param heat: heat produced over the trajectory
    @type heat: float
    @param work: work produced during the trajectory
    @type work: float
    """
    
    def __init__(self, heat=0.0, work=0.0):
        self._heat = heat
        self._work = work
        self._states = []
        
    @staticmethod
    def create(full=True):
        """
        Trajectory builder factory.

        @param full: if True, a TrajectoryBuilder instance designed
                     to build a full trajectory with initial state,
                     intermediate states and a final state. If False,
                     a ShortTrajectoryBuilder instance designed to
                     hold only the initial and the final state is
                     returned
        @type full: boolean
        """
        
        if full:
            return TrajectoryBuilder()
        else:
            return ShortTrajectoryBuilder()
        
    @property
    def product(self):
        """
        The L{Trajectory} instance build by a specific instance of
        this class
        """
        return Trajectory(self._states, heat=self._heat, work=self._work)

    def add_initial_state(self, state):
        """
        Inserts a state at the beginning of the trajectory

        @param state: state to be added
        @type state: L{State}
        """
        self._states.insert(0, state.clone())
        
    def add_intermediate_state(self, state):
        """
        Adds a state to the end of the trajectory

        @param state: state to be added
        @type state: L{State}
        """
        self._states.append(state.clone())
    
    def add_final_state(self, state):
        """
        Adds a state to the end of the trajectory

        @param state: state to be added
        @type state: L{State}
        """
        self._states.append(state.clone())
    
class ShortTrajectoryBuilder(TrajectoryBuilder):    

    def add_intermediate_state(self, state):
        pass

    @property
    def product(self):
        """
        The L{PropagationResult} instance built by a specific instance of
        this class
        """
        
        if len(self._states) != 2:
            raise ValueError("Can't create a product, two states required")
        
        initial, final = self._states
        return PropagationResult(initial, final, heat=self._heat)


class MCCollection(csb.core.BaseCollectionContainer):
    """
    Collection of single-chain samplers.

    @param items: samplers
    @type items: list of L{AbstractSingleChainMC}
    """
    
    def __init__(self, items):

        from csb.statistics.samplers.mc.singlechain import AbstractSingleChainMC
        
        super(MCCollection, self).__init__(items, type=AbstractSingleChainMC)


class AbstractSwapScheme(object):
    """
    Provides the interface for classes defining schemes according to which swaps in
    Replica Exchange-like simulations are performed.

    @param algorithm: Exchange algorithm that performs the swaps
    @type algorithm: L{AbstractExchangeMC}
    """

    __metaclass__ = ABCMeta

    def __init__(self, algorithm):

        self._algorithm = algorithm

    @abstractmethod
    def swap_all(self):
        """
        Advises the Replica Exchange-like algorithm to perform swaps according to
        the schedule defined here.
        """
        
        pass
    
class AlternatingAdjacentSwapScheme(AbstractSwapScheme):
    """
    Provides a swapping scheme in which tries exchanges between neighbours only
    following the scheme 1 <-> 2, 3 <-> 4, ... and after a sampling period 2 <-> 3, 4 <-> 5, ...

    @param algorithm: Exchange algorithm that performs the swaps
    @type algorithm: L{AbstractExchangeMC}
    """

    def __init__(self, algorithm):

        super(AlternatingAdjacentSwapScheme, self).__init__(algorithm)
        
        self._current_swap_list = None
        self._swap_list1 = []
        self._swap_list2 = []
        self._create_swap_lists()
    
    def _create_swap_lists(self):

        if len(self._algorithm.param_infos) == 1:
            self._swap_list1.append(0)
            self._swap_list2.append(0)
        else:
            i = 0
            while i < len(self._algorithm.param_infos):
                self._swap_list1.append(i)
                i += 2
                
            i = 1
            while i < len(self._algorithm.param_infos):
                self._swap_list2.append(i)
                i += 2

        self._current_swap_list = self._swap_list1

    def swap_all(self):
        
        for x in self._current_swap_list:
            self._algorithm.swap(x)

        if self._current_swap_list == self._swap_list1:
            self._current_swap_list = self._swap_list2
        else:
            self._current_swap_list = self._swap_list1
