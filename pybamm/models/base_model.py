#
# Base model class
#
import inspect
import numbers
import pybamm
import warnings


class ParamClass:
    """Class for converting a module of parameters into a class. For pickling."""

    def __init__(self, methods):
        for k, v in methods.__dict__.items():
            # don't save module attributes (e.g. pybamm, numpy)
            if not (k.startswith("__") or inspect.ismodule(v)):
                self.__dict__[k] = v


class BaseModel(object):
    """Base model class for other models to extend.

    Attributes
    ----------

    name: str
        A string giving the name of the model
    options: dict
        A dictionary of options to be passed to the model
    rhs: dict
        A dictionary that maps expressions (variables) to expressions that represent
        the rhs
    algebraic: dict
        A dictionary that maps expressions (variables) to expressions that represent
        the algebraic equations. The algebraic expressions are assumed to equate
        to zero. Note that all the variables in the model must exist in the keys of
        `rhs` or `algebraic`.
    initial_conditions: dict
        A dictionary that maps expressions (variables) to expressions that represent
        the initial conditions for the state variables y. The initial conditions for
        algebraic variables are provided as initial guesses to a root finding algorithm
        that calculates consistent initial conditions.
    boundary_conditions: dict
        A dictionary that maps expressions (variables) to expressions that represent
        the boundary conditions
    variables: dict
        A dictionary that maps strings to expressions that represent
        the useful variables
    events: list of :class:`pybamm.Event`
        A list of events. Each event can either cause the solver to terminate
        (e.g. concentration goes negative), or be used to inform the solver of the
        existance of a discontinuity (e.g. discontinuity in the input current)
    concatenated_rhs : :class:`pybamm.Concatenation`
        After discretisation, contains the expressions representing the rhs equations
        concatenated into a single expression
    concatenated_algebraic : :class:`pybamm.Concatenation`
        After discretisation, contains the expressions representing the algebraic
        equations concatenated into a single expression
    concatenated_initial_conditions : :class:`numpy.array`
        After discretisation, contains the vector of initial conditions
    mass_matrix : :class:`pybamm.Matrix`
        After discretisation, contains the mass matrix for the model. This is computed
        automatically
    mass_matrix_inv : :class:`pybamm.Matrix`
        After discretisation, contains the inverse mass matrix for the differential
        (rhs) part of model. This is computed automatically
    jacobian : :class:`pybamm.Concatenation`
        Contains the Jacobian for the model. If model.use_jacobian is True, the
        Jacobian is computed automatically during solver set up
    jacobian_rhs : :class:`pybamm.Concatenation`
        Contains the Jacobian for the part of the model which contains time derivatives.
        If model.use_jacobian is True, the Jacobian is computed automatically during
        solver set up
    jacobian_algebraic : :class:`pybamm.Concatenation`
        Contains the Jacobian for the algebraic part of the model. This may be used
        by the solver when calculating consistent initial conditions. If
        model.use_jacobian is True, the Jacobian is computed automatically during
        solver set up
    use_jacobian : bool
        Whether to use the Jacobian when solving the model (default is True)
    use_simplify : bool
        Whether to simplify the expression tress representing the rhs and
        algebraic equations, Jacobain (if using) and events, before solving the
        model (default is True)
    convert_to_format : str
        Whether to convert the expression trees representing the rhs and
        algebraic equations, Jacobain (if using) and events into a different format:

        - None: keep PyBaMM expression tree structure.
        - "python": convert into pure python code that will calculate the result of \
        calling `evaluate(t, y)` on the given expression treeself.
        - "casadi": convert into CasADi expression tree, which then uses CasADi's \
        algorithm to calculate the Jacobian.

        Default is "casadi".

    """

    def __init__(self, name="Unnamed model"):
        self.name = name
        self.options = {}

        # Initialise empty model
        self._rhs = {}
        self._algebraic = {}
        self._initial_conditions = {}
        self._boundary_conditions = {}
        self._variables = pybamm.FuzzyDict()
        self._events = []
        self._concatenated_rhs = None
        self._concatenated_algebraic = None
        self._concatenated_initial_conditions = None
        self._mass_matrix = None
        self._mass_matrix_inv = None
        self._jacobian = None
        self._jacobian_algebraic = None
        self.external_variables = []

        # Default behaviour is to use the jacobian and simplify
        self.use_jacobian = True
        self.use_simplify = True
        self.convert_to_format = "casadi"

    def _set_dictionary(self, dict, name):
        """
        Convert any scalar equations in dict to 'pybamm.Scalar'
        and check that domains are consistent
        """
        # Convert any numbers to a pybamm.Scalar
        for var, eqn in dict.items():
            if isinstance(eqn, numbers.Number):
                dict[var] = pybamm.Scalar(eqn)

        if not all(
            [
                variable.domain == equation.domain
                or variable.domain == []
                or equation.domain == []
                for variable, equation in dict.items()
            ]
        ):
            raise pybamm.DomainError(
                "variable and equation in '{}' must have the same domain".format(name)
            )

        return dict

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def rhs(self):
        return self._rhs

    @rhs.setter
    def rhs(self, rhs):
        self._rhs = self._set_dictionary(rhs, "rhs")

    @property
    def algebraic(self):
        return self._algebraic

    @algebraic.setter
    def algebraic(self, algebraic):
        self._algebraic = self._set_dictionary(algebraic, "algebraic")

    @property
    def initial_conditions(self):
        return self._initial_conditions

    @initial_conditions.setter
    def initial_conditions(self, initial_conditions):
        self._initial_conditions = self._set_dictionary(
            initial_conditions, "initial_conditions"
        )

    @property
    def boundary_conditions(self):
        return self._boundary_conditions

    @boundary_conditions.setter
    def boundary_conditions(self, boundary_conditions):
        # Convert any numbers to a pybamm.Scalar
        for var, bcs in boundary_conditions.items():
            for side, bc in bcs.items():
                if isinstance(bc[0], numbers.Number):
                    # typ is the type of the bc, e.g. "Dirichlet" or "Neumann"
                    eqn, typ = boundary_conditions[var][side]
                    boundary_conditions[var][side] = (pybamm.Scalar(eqn), typ)
                # Check types
                if bc[1] not in ["Dirichlet", "Neumann"]:
                    raise pybamm.ModelError(
                        """
                        boundary condition types must be Dirichlet or Neumann, not '{}'
                        """.format(
                            bc[1]
                        )
                    )
        self._boundary_conditions = boundary_conditions

    @property
    def variables(self):
        return self._variables

    @variables.setter
    def variables(self, variables):
        self._variables = pybamm.FuzzyDict(variables)

    def variable_names(self):
        return list(self._variables.keys())

    @property
    def events(self):
        return self._events

    @events.setter
    def events(self, events):
        self._events = events

    @property
    def concatenated_rhs(self):
        return self._concatenated_rhs

    @concatenated_rhs.setter
    def concatenated_rhs(self, concatenated_rhs):
        self._concatenated_rhs = concatenated_rhs

    @property
    def concatenated_algebraic(self):
        return self._concatenated_algebraic

    @concatenated_algebraic.setter
    def concatenated_algebraic(self, concatenated_algebraic):
        self._concatenated_algebraic = concatenated_algebraic

    @property
    def concatenated_initial_conditions(self):
        return self._concatenated_initial_conditions

    @concatenated_initial_conditions.setter
    def concatenated_initial_conditions(self, concatenated_initial_conditions):
        self._concatenated_initial_conditions = concatenated_initial_conditions

    @property
    def mass_matrix(self):
        return self._mass_matrix

    @mass_matrix.setter
    def mass_matrix(self, mass_matrix):
        self._mass_matrix = mass_matrix

    @property
    def mass_matrix_inv(self):
        return self._mass_matrix_inv

    @mass_matrix_inv.setter
    def mass_matrix_inv(self, mass_matrix_inv):
        self._mass_matrix_inv = mass_matrix_inv

    @property
    def jacobian(self):
        return self._jacobian

    @jacobian.setter
    def jacobian(self, jacobian):
        self._jacobian = jacobian

    @property
    def jacobian_rhs(self):
        return self._jacobian_rhs

    @jacobian_rhs.setter
    def jacobian_rhs(self, jacobian_rhs):
        self._jacobian_rhs = jacobian_rhs

    @property
    def jacobian_algebraic(self):
        return self._jacobian_algebraic

    @jacobian_algebraic.setter
    def jacobian_algebraic(self, jacobian_algebraic):
        self._jacobian_algebraic = jacobian_algebraic

    @property
    def param(self):
        return self._param

    @param.setter
    def param(self, values):
        # convert module into a class
        # (StackOverflow: https://tinyurl.com/yk3euon3)
        self._param = ParamClass(values)

    @property
    def options(self):
        return self._options

    @options.setter
    def options(self, options):
        self._options = options

    def __getitem__(self, key):
        return self.rhs[key]

    def new_copy(self, options=None):
        "Create an empty copy with identical options, or new options if specified"
        options = options or self.options
        new_model = self.__class__(options)
        new_model.name = self.name
        new_model.use_jacobian = self.use_jacobian
        new_model.use_simplify = self.use_simplify
        new_model.convert_to_format = self.convert_to_format
        return new_model

    def update(self, *submodels):
        """
        Update model to add new physics from submodels

        Parameters
        ----------
        submodel : iterable of :class:`pybamm.BaseModel`
            The submodels from which to create new model
        """
        for submodel in submodels:

            # check and then update dicts
            self.check_and_combine_dict(self._rhs, submodel.rhs)
            self.check_and_combine_dict(self._algebraic, submodel.algebraic)
            self.check_and_combine_dict(
                self._initial_conditions, submodel.initial_conditions
            )
            self.check_and_combine_dict(
                self._boundary_conditions, submodel.boundary_conditions
            )
            self.variables.update(submodel.variables)  # keys are strings so no check
            self._events += submodel.events

    def check_and_combine_dict(self, dict1, dict2):
        # check that the key ids are distinct
        ids1 = set(x.id for x in dict1.keys())
        ids2 = set(x.id for x in dict2.keys())
        if len(ids1.intersection(ids2)) != 0:
            variables = [x for x in dict1.keys() if x.id in ids1.intersection(ids2)]
            raise pybamm.ModelError(
                "Submodel incompatible: duplicate variables '{}'".format(variables)
            )
        dict1.update(dict2)

    def check_well_posedness(self, post_discretisation=False):
        """
        Check that the model is well-posed by executing the following tests:
        - Model is not over- or underdetermined, by comparing keys and equations in rhs
        and algebraic. Overdetermined if more equations than variables, underdetermined
        if more variables than equations.
        - There is an initial condition in self.initial_conditions for each
        variable/equation pair in self.rhs
        - There are appropriate boundary conditions in self.boundary_conditions for each
        variable/equation pair in self.rhs and self.algebraic

        Parameters
        ----------
        post_discretisation : boolean
            A flag indicating tests to be skipped after discretisation
        """
        self.check_well_determined(post_discretisation)
        self.check_algebraic_equations(post_discretisation)
        self.check_ics_bcs()
        self.check_default_variables_dictionaries()
        # Can't check variables after discretising, since Variable objects get replaced
        # by StateVector objects
        # Checking variables is slow, so only do it in debug mode
        if pybamm.settings.debug_mode is True and post_discretisation is False:
            self.check_variables()

    def check_well_determined(self, post_discretisation):
        """ Check that the model is not under- or over-determined. """
        # Equations (differential and algebraic)
        # Get all the variables from differential and algebraic equations
        vars_in_rhs_keys = set()
        vars_in_algebraic_keys = set()
        vars_in_eqns = set()
        # Get all variables ids from rhs and algebraic keys and equations, and
        # from boundary conditions
        # For equations we look through the whole expression tree.
        # "Variables" can be Concatenations so we also have to look in the whole
        # expression tree
        for var, eqn in self.rhs.items():
            vars_in_rhs_keys.update(
                [x.id for x in var.pre_order() if isinstance(x, pybamm.Variable)]
            )
            vars_in_eqns.update(
                [x.id for x in eqn.pre_order() if isinstance(x, pybamm.Variable)]
            )
        for var, eqn in self.algebraic.items():
            vars_in_algebraic_keys.update(
                [x.id for x in var.pre_order() if isinstance(x, pybamm.Variable)]
            )
            vars_in_eqns.update(
                [x.id for x in eqn.pre_order() if isinstance(x, pybamm.Variable)]
            )
        for var, side_eqn in self.boundary_conditions.items():
            for side, (eqn, typ) in side_eqn.items():
                vars_in_eqns.update(
                    [x.id for x in eqn.pre_order() if isinstance(x, pybamm.Variable)]
                )
        # If any keys are repeated between rhs and algebraic then the model is
        # overdetermined
        if not set(vars_in_rhs_keys).isdisjoint(vars_in_algebraic_keys):
            raise pybamm.ModelError("model is overdetermined (repeated keys)")
        # If any algebraic keys don't appear in the eqns (or bcs) then the model is
        # overdetermined (but rhs keys can be absent from the eqns, e.g. dcdt = -1 is
        # fine)
        # Skip this step after discretisation, as any variables in the equations will
        # have been discretised to slices but keys will still be variables
        extra_algebraic_keys = vars_in_algebraic_keys.difference(vars_in_eqns)
        if extra_algebraic_keys and not post_discretisation:
            raise pybamm.ModelError("model is overdetermined (extra algebraic keys)")
        # If any variables in the equations don't appear in the keys then the model is
        # underdetermined
        vars_in_keys = vars_in_rhs_keys.union(vars_in_algebraic_keys)
        extra_variables_in_equations = vars_in_eqns.difference(vars_in_keys)

        # get ids of external variables
        external_ids = {var.id for var in self.external_variables}
        for var in self.external_variables:
            if isinstance(var, pybamm.Concatenation):
                child_ids = {child.id for child in var.children}
                external_ids = external_ids.union(child_ids)

        extra_variables = extra_variables_in_equations.difference(external_ids)

        if extra_variables:
            raise pybamm.ModelError("model is underdetermined (too many variables)")

    def check_algebraic_equations(self, post_discretisation):
        """
        Check that the algebraic equations are well-posed.
        Before discretisation, each algebraic equation key must appear in the equation
        After discretisation, there must be at least one StateVector in each algebraic
        equation
        """
        vars_in_bcs = set()
        for var, side_eqn in self.boundary_conditions.items():
            for eqn, _ in side_eqn.values():
                vars_in_bcs.update(
                    [x.id for x in eqn.pre_order() if isinstance(x, pybamm.Variable)]
                )
        if not post_discretisation:
            # After the model has been defined, each algebraic equation key should
            # appear in that algebraic equation, or in the boundary conditions
            # this has been relaxed for concatenations for now
            for var, eqn in self.algebraic.items():
                if not (
                    any(x.id == var.id for x in eqn.pre_order())
                    or var.id in vars_in_bcs
                    or isinstance(var, pybamm.Concatenation)
                ):
                    raise pybamm.ModelError(
                        "each variable in the algebraic eqn keys must appear in the eqn"
                    )
        else:
            # variables in keys don't get discretised so they will no longer match
            # with the state vectors in the algebraic equations. Instead, we check
            # that each algebraic equation contains some StateVector
            for eqn in self.algebraic.values():
                if not any(isinstance(x, pybamm.StateVector) for x in eqn.pre_order()):
                    raise pybamm.ModelError(
                        "each algebraic equation must contain at least one StateVector"
                    )

    def check_ics_bcs(self):
        """ Check that the initial and boundary conditions are well-posed. """
        # Initial conditions
        for var in self.rhs.keys():
            if var not in self.initial_conditions.keys():
                raise pybamm.ModelError(
                    """no initial condition given for variable '{}'""".format(var)
                )

        # Boundary conditions
        for var, eqn in {**self.rhs, **self.algebraic}.items():
            if eqn.has_symbol_of_classes(
                (pybamm.Gradient, pybamm.Divergence)
            ) and not eqn.has_symbol_of_classes(pybamm.Integral):
                # I have relaxed this check for now so that the lumped temperature
                # equation doesn't raise errors (this has and average in it)

                # Variable must be in the boundary conditions
                if not any(
                    var.id == x.id
                    for symbol in self.boundary_conditions.keys()
                    for x in symbol.pre_order()
                ):
                    raise pybamm.ModelError(
                        """
                        no boundary condition given for
                        variable '{}' with equation '{}'.
                        """.format(
                            var, eqn
                        )
                    )

    def check_default_variables_dictionaries(self):
        """ Chec that the right variables are provided. """
        missing_vars = []
        for output, expression in self._variables.items():
            if expression is None:
                missing_vars.append(output)
        if len(missing_vars) > 0:
            warnings.warn(
                "the standard output variable(s) '{}' have not been supplied. "
                "These may be required for testing or comparison with other "
                "models.".format(missing_vars),
                pybamm.ModelWarning,
                stacklevel=2,
            )
            # Remove missing entries
            for output in missing_vars:
                del self._variables[output]

    def check_variables(self):
        # Create list of all Variable nodes that appear in the model's list of variables
        all_vars = {}
        for eqn in self.variables.values():
            # Add all variables in the equation to the list of variables
            all_vars.update(
                {x.id: x for x in eqn.pre_order() if isinstance(x, pybamm.Variable)}
            )
        var_ids_in_keys = set()

        model_and_external_variables = (
            list(self.rhs.keys())
            + list(self.algebraic.keys())
            + self.external_variables
        )

        for var in model_and_external_variables:
            if isinstance(var, pybamm.Variable):
                var_ids_in_keys.add(var.id)
            # Key can be a concatenation
            elif isinstance(var, pybamm.Concatenation):
                var_ids_in_keys.update([child.id for child in var.children])

        for var_id, var in all_vars.items():
            if var_id not in var_ids_in_keys:
                raise pybamm.ModelError(
                    """
                    No key set for variable '{}'. Make sure it is included in either
                    model.rhs, model.algebraic, or model.external_variables in an
                    unmodified form (e.g. not Broadcasted)
                    """.format(
                        var
                    )
                )

    @property
    def default_solver(self):
        "Return default solver based on whether model is ODE model or DAE model"
        if len(self.algebraic) == 0:
            return pybamm.ScipySolver()
        elif pybamm.have_idaklu() and self.use_jacobian is True:
            # KLU solver requires jacobian to be provided
            return pybamm.IDAKLUSolver()
        else:
            return pybamm.CasadiSolver(mode="safe")
