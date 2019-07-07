#
# Test base full surface form stefan maxwell electrolyte conductivity submodel
#

import pybamm
import tests
import unittest


class TestBaseFull(unittest.TestCase):
    def test_public_functions(self):
        param = pybamm.standard_parameters_lithium_ion
        a = pybamm.Scalar(0)
        a_n = pybamm.Broadcast(pybamm.Scalar(0), ["negative electrode"])
        a_s = pybamm.Broadcast(pybamm.Scalar(0), ["separator"])
        a_p = pybamm.Broadcast(pybamm.Scalar(0), ["positive electrode"])
        variables = {
            "Current collector current density": a,
            "Negative electrode porosity": a_n,
            "Negative electrolyte concentration": a_n,
        }

        spf = pybamm.electrolyte.stefan_maxwell.conductivity.surface_potential_form
        submodel = spf.BaseFull(param, "Negative")
        std_tests = tests.StandardSubModelTests(submodel, variables)
        std_tests.test_all()

        variables = {
            "Current collector current density": a,
            "Negative electrolyte potential": a_n,
            "Negative electrolyte current density": a_n,
            "Separator electrolyte potential": a_s,
            "Separator electrolyte current density": a_s,
            "Positive electrode porosity": a_p,
            "Positive electrolyte concentration": a_p,
        }
        submodel = spf.BaseFull(param, "Positive")
        std_tests = tests.StandardSubModelTests(submodel, variables)
        std_tests.test_all()


if __name__ == "__main__":
    print("Add -v for more debug output")
    import sys

    if "-v" in sys.argv:
        debug = True
    unittest.main()