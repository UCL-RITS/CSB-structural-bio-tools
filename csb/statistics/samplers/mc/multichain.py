"""
Implements several extended-ensemble Monte Carlo sampling algorithms.

Here is a short example which shows how to sample from a PDF using the replica
exchange with non-equilibrium switches (RENS) method. It draws 5000 samples from
a 1D normal distribution using the RENS algorithm working on three Markov chains
being generated by the HMC algorithm:


    >>> import numpy
    >>> from numpy import sqrt
    >>> from csb.io.plots import Chart
    >>> from csb.statistics.pdf import Normal
    >>> from csb.statistics.samplers import State
    >>> from csb.statistics.samplers.mc import ThermostattedMDRENSSwapParameterInfo, AlternatingAdjacentSwapScheme
    >>> from csb.statistics.samplers.mc.multichain import ThermostattedMDRENS
    >>> from csb.statistics.samplers.mc.singlechain import HMCSampler

    >>> # Pick some initial state for the different Markov chains:
    >>> initial_state = State(numpy.array([1.]))

    >>> # Set standard deviations:
    >>> std_devs = [1./sqrt(5), 1. / sqrt(3), 1.]

    >>> # Set HMC timesteps and trajectory length:
    >>> hmc_timesteps = [0.6, 0.7, 0.6]
    >>> hmc_trajectory_length = 20
    >>> hmc_gradients = [lambda q, t: 1 / (std_dev ** 2) * q for std_dev in std_devs]

    >>> # Set parameters for the thermostatted RENS algorithm:
    >>> rens_trajectory_length = 30
    >>> rens_timesteps = [0.3, 0.5]

    >>> # Set interpolation gradients as a function of the work parameter l:
    >>> rens_gradients = [lambda q, l, i=i: (l / (std_devs[i + 1] ** 2) + (1 - l) / (std_devs[i] ** 2)) * q 
                          for i in range(len(std_devs)-1)]

    >>> # Initialize HMC samplers:
    >>> samplers = [HMCSampler(Normal(sigma=std_devs[i]), initial_state, hmc_gradients[i], hmc_timesteps[i],
                    hmc_trajectory_length) for i in range(len(std_devs))]

    >>> # Create swap parameter objects:
    params = [ThermostattedMDRENSSwapParameterInfo(samplers[0], samplers[1], rens_timesteps[0],
              rens_trajectory_length, rens_gradients[0]),
              ThermostattedMDRENSSwapParameterInfo(samplers[1], samplers[2], rens_timesteps[1],
              rens_trajectory_length, rens_gradients[1])]

    >>> # Initialize thermostatted RENS algorithm:
    >>> algorithm = ThermostattedMDRENS(samplers, params)

    >>> # Initialize swapping scheme:
    >>> swapper = AlternatingAdjacentSwapScheme(algorithm)

    >>> # Initialize empty list which will store the samples:
    >>> states = []
    >>> for i in range(5000):
            if i % 5 == 0:
                swapper.swap_all()
            states.append(algorithm.sample())

    >>> # Print acceptance rates:
    >>> print('HMC acceptance rates:', [s.acceptance_rate for s in samplers])
    >>> print('swap acceptance rates:', algorithm.acceptance_rates)

    >>> # Create and plot histogram for first sampler and numpy.random.normal reference:
    >>> chart = Chart()
    >>> rawstates = [state[0].position[0] for state in states]
    >>> chart.plot.hist([numpy.random.normal(size=5000, scale=std_devs[0]), rawstates], bins=30, normed=True)
    >>> chart.plot.legend(['numpy.random.normal', 'RENS + HMC'])
    >>> chart.show()


For L{ReplicaExchangeMC} (RE), the procedure is easier because apart from the
two sampler instances the corresponding L{RESwapParameterInfo} objects take
no arguments.

Every replica exchange algorithm in this module (L{ReplicaExchangeMC}, L{MDRENS},
L{ThermostattedMDRENS}) is used in a similar way. A simulation is always
initialized with a list of samplers (instances of classes derived from
L{AbstractSingleChainMC}) and a list of L{AbstractSwapParameterInfo} objects
suited for the algorithm under consideration. Every L{AbstractSwapParameterInfo}
object holds all the information needed to perform a swap between two samplers.
The usual scheme is to swap only adjacent replicae in a scheme::

    1 <--> 2, 3 <--> 4, ...
    2 <--> 3, 4 <--> 5, ...
    1 <--> 2, 3 <--> 4, ...
    
This swapping scheme is implemented in the L{AlternatingAdjacentSwapScheme} class,
but different schemes can be easily implemented by deriving from L{AbstractSwapScheme}.
Then the simulation is run by looping over the number of samples to be drawn
and calling the L{AbstractExchangeMC.sample} method of the algorithm. By calling
the L{AbstractSwapScheme.swap_all} method of the specific L{AbstractSwapScheme}
implementation, all swaps defined in the list of L{AbstractSwapParameterInfo}
objects are performed according to the swapping scheme. The
L{AbstractSwapScheme.swap_all} method may be called for example after sampling
intervals of a fixed length or randomly.
"""

import csb.numeric

from csb.statistics.samplers.mc import AbstractExchangeMC, AbstractRENS, RESwapCommunicator
from csb.statistics.samplers.mc.propagators import MDPropagator, ThermostattedMDPropagator
from csb.statistics.samplers.mc import Trajectory
from csb.numeric.integrators import AbstractGradient


class InterpolationFactory(object):
    """
    Produces interpolations for functions changed during non-equilibrium
    trajectories.
    
    @param protocol: protocol to be used to generate non-equilibrium trajectories
    @type protocol: function mapping t to [0...1] for fixed tau
    @param tau: switching time
    @type tau: float    
    """
    
    def __init__(self, protocol, tau):
        
        self._protocol = None
        self._tau = None
        
        self.protocol = protocol
        self.tau = tau
        
    @property
    def protocol(self):
        return self._protocol
    @protocol.setter
    def protocol(self, value):
        if not hasattr(value, '__call__'):
            raise TypeError(value)
        self._protocol = value
                    
    @property
    def tau(self):
        return self._tau
    @tau.setter
    def tau(self, value):
        self._tau = float(value)
        
    def build_gradient(self, gradient):
        """
        Create a gradient instance with according to given protocol
        and switching time.
        
        @param gradient: gradient with G(0) = G_1 and G(1) = G_2
        @type gradient: callable    
        """
        return Gradient(gradient, self._protocol, self._tau)
    
    def build_temperature(self, temperature):
        """
        Create a temperature function according to given protocol and
        switching time.

        @param temperature: temperature with T(0) = T_1 and T(1) = T_2
        @type temperature: callable        
        """
        return lambda t: temperature(self.protocol(t, self.tau))
        
class Gradient(AbstractGradient):
    
    def __init__(self, gradient, protocol, tau):
        
        self._protocol = protocol
        self._gradient = gradient
        self._tau = tau
    
    def evaluate(self, q, t):
        return self._gradient(q, self._protocol(t, self._tau))

class ReplicaExchangeMC(AbstractExchangeMC):
    """
    Replica Exchange (RE, Swendsen & Yang 1986) implementation.
    """
        
    def _propose_swap(self, param_info):
        
        return RESwapCommunicator(param_info, Trajectory([param_info.sampler1.state,
                                                          param_info.sampler1.state]),
                                              Trajectory([param_info.sampler2.state,
                                                          param_info.sampler2.state]))
    
    def _calc_pacc_swap(self, swapcom):
        
        E1 = lambda x:-swapcom.sampler1._pdf.log_prob(x)
        E2 = lambda x:-swapcom.sampler2._pdf.log_prob(x)

        T1 = swapcom.sampler1.temperature
        T2 = swapcom.sampler2.temperature
        
        state1 = swapcom.traj12.initial
        state2 = swapcom.traj21.initial
        
        proposal1 = swapcom.traj21.final
        proposal2 = swapcom.traj12.final

        swapcom.acceptance_probability = csb.numeric.exp(-E1(proposal1.position) / T1 
                                                         + E1(state1.position) / T1 
                                                         - E2(proposal2.position) / T2 
                                                         + E2(state2.position) / T2)
                                                 
        return swapcom

class MDRENS(AbstractRENS):
    """
    Replica Exchange with Nonequilibrium Switches (RENS, Ballard & Jarzynski 2009)
    with Molecular Dynamics (MD) trajectories.

    @param samplers: Samplers which sample their
                         respective equilibrium distributions
    @type samplers: list of L{AbstractSingleChainMC}

    @param param_infos: ParameterInfo instance holding
                        information required to perform a MDRENS swap
    @type param_infos: list of L{MDRENSSwapParameterInfo}

    @param integrator: Subclass of L{AbstractIntegrator} to be used to
                       calculate the non-equilibrium trajectories
    @type integrator: type
    """

    def __init__(self, samplers, param_infos,
                 integrator=csb.numeric.integrators.FastLeapFrog):
        
        super(MDRENS, self).__init__(samplers, param_infos)
        
        self._integrator = integrator
        
    def _run_traj_generator(self, traj_info):
        
        tau = traj_info.param_info.traj_length * traj_info.param_info.timestep
        factory = InterpolationFactory(traj_info.protocol, tau)

        gen = MDPropagator(factory.build_gradient(traj_info.param_info.gradient),
                           traj_info.param_info.timestep,
						   mass_matrix=traj_info.param_info.mass_matrix,
						   integrator=self._integrator)
        
        traj = gen.generate(traj_info.init_state, int(traj_info.param_info.traj_length))
        return traj

class ThermostattedMDRENS(MDRENS):
    """
    Replica Exchange with Nonequilibrium Switches (RENS, Ballard & Jarzynski, 2009)
    with Andersen-thermostatted Molecular Dynamics (MD) trajectories.

    @param samplers: Samplers which sample their
                         respective equilibrium distributions
    @type samplers: list of L{AbstractSingleChainMC}

    @param param_infos: ParameterInfo instance holding
                        information required to perform a MDRENS swap
    @type param_infos: list of L{ThermostattedMDRENSSwapParameterInfo}

    @param integrator: Subclass of L{AbstractIntegrator} to be used to
                       calculate the non-equilibrium trajectories
    @type integrator: type
    """

    def __init__(self, samplers, param_infos, integrator=csb.numeric.integrators.LeapFrog):
        
        super(ThermostattedMDRENS, self).__init__(samplers, param_infos, integrator)

    def _run_traj_generator(self, traj_info):
        
        tau = traj_info.param_info.traj_length * traj_info.param_info.timestep
        factory = InterpolationFactory(traj_info.protocol, tau)
        
        grad = factory.build_gradient(traj_info.param_info.gradient)
        temp = factory.build_temperature(traj_info.param_info.temperature)
        
        gen = ThermostattedMDPropagator(grad,
                                        traj_info.param_info.timestep, temperature=temp, 
										collision_probability=traj_info.param_info.collision_probability,
                                        update_interval=traj_info.param_info.collision_interval,
										mass_matrix=traj_info.param_info.mass_matrix,
                                        integrator=self._integrator)
        
        traj = gen.generate(traj_info.init_state, traj_info.param_info.traj_length)

        return traj
