# Copyright (c) [2024-2025] [Laszlo Oroszlany, Daniel Pozsar]
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""pair

_extended_summary_
"""
import copy
from typing import Union

import numpy as np
import sisl
from numpy.typing import NDArray

from .. import __version__
from .._core.core import onsite_projection
from .magnetic_entity import MagneticEntity
from .utilities import (
    calculate_exchange_tensor,
    fit_exchange_tensor,
    interaction_energy,
)


class Pair:
    """This class contains the data and the methods related to the pairs of magnetic entities.

    It sets up the instance based on the Hamiltonian of the DFT calculation, a pair of
    MagneticEntities and the supercell shift of the second MagneticEntities, given that the first
    one is not shifted. By default ``dh`` is ``None`` and we use the Hamiltonian from the magnetic
    entities. If the Hamiltonian from the two magnetic entities are different it raises an error.

    Parameters
    ----------
    M1: MagneticEntity
        The first magnetic entity
    M2: MagneticEntity
        The second magnetic entity
    supercell_shift: Union[list, NDArray]
        The integer coordinates of the supercell shift

    Examples
    --------
    The following examples show you how to create pairs in the **Fe3GeTe2** system.

    >>> fdf_path = "/Users/danielpozsar/Downloads/nojij/Fe3GeTe2/monolayer/soc/lat3_791/Fe3GeTe2.fdf"

    >>> Fe3 = MagneticEntity(fdf_path, atom=3, l=2)
    >>> Fe5 = MagneticEntity(fdf_path, atom=5, l=2)
    >>> pair_of_Fe = Pair(Fe3, Fe5, [0,0,0])
    >>> print(pair_of_Fe)
    <grogupy.Pair tag1=3Fe(l:2), tag2=5Fe(l:2), Ruc=[0 0 0]>

    Methods
    -------
    calculate_energies(weights) :
        Calculates the energies of the infinitesimal rotations.
    calculate_exchange_tensor() :
        Calculates the exchange tensor from the energies.
    fit_exchange_tensor(ref_xcf) :
        Fits the exchange tensor to the energies.
    to_dict(all) :
        Returns the instance data as a dictionary.
    add_G_tmp(i, Gk, k, weight) :
        Adds the calculated Greens function to the temporary Greens function.
    copy() :
        Return a copy of this Pair

    Attributes
    ----------
    M1: MagneticEntity
        The first magnetic entity
    M2: MagneticEntity
        The second magnetic entity
    supercell_shift: NDArray
        The supercell shift normed by the supercell vectors
    cell: NDArray
        The supercell vectors
    Gij: list
        Projected Greens function from M1 to M2
    Gji: list
        Projected Greens function from M2 to M1
    SBS1: int
        The SPIN BOX size of M1
    SBS2: int
        The SPIN BOX size of M2
    SBI1: NDArray
        The SPIN BOX indices of M1
    SBI2: NDArray
        The SPIN BOX indices of M2
    tags: list[str]
        The tags of the two magnetic entities
    supercell_shift_xyz: NDArray
        The supercell shift in real coordinates
    xyz: list[NDArray, NDArray]
        The coordinates of the magnetic entity (it can consist of many atoms)
    xyz_center: list[NDArray, NDArray]
        The center of coordinates for the magnetic entities
    distance: float
        The distance of the magnetic entities (it uses the center of coordinates
        for each magnetic entity)
    energies : Union[None, NDArray]
        The calculated energies for each direction
    self.J_iso: Union[float, None]
        Isotropic exchange, by default None
    self.J: Union[NDArray, None]
        Complete exchange tensor, by default None
    self.J_S: Union[NDArray, None]
        Symmetric exchange, by default None
    self.D: Union[NDArray, None]
        Dzyaloshinskii-Morilla vector, by default None

    Raises
    ------
    Exception
        Different Hamiltonians from the magnetic entities

    """

    number_of_pairs: int = 0

    def __init__(
        self,
        M1: MagneticEntity,
        M2: MagneticEntity,
        supercell_shift: Union[list, NDArray] = np.array([0, 0, 0]),
    ) -> None:
        """This class contains the data and the methods related to the pairs of magnetic entities.

        It sets up the instance based on the Hamiltonian of the DFT calculation, a pair of
        MagneticEntities and the supercell shift of the second MagneticEntities, given that the first
        one is not shifted. By default ``dh`` is ``None`` and we use the Hamiltonian from the magnetic
        entities. If the Hamiltonian from the two magnetic entities are different it raises an error.

        Parameters
        ----------
        M1: MagneticEntity
            The first magnetic entity
        M2: MagneticEntity
            The second magnetic entity
        supercell_shift: Union[list, NDArray]
            The integer coordinates of the supercell shift

        Examples
        --------
        The following examples show you how to create pairs in the **Fe3GeTe2** system.

        >>> fdf_path = "/Users/danielpozsar/Downloads/nojij/Fe3GeTe2/monolayer/soc/lat3_791/Fe3GeTe2.fdf"

        >>> Fe3 = MagneticEntity(fdf_path, atom=3, l=2)
        >>> Fe5 = MagneticEntity(fdf_path, atom=5, l=2)
        >>> pair_of_Fe = Pair(Fe3, Fe5, [0,0,0])
        >>> print(pair_of_Fe)
        <grogupy.Pair tag1=3Fe(l:2), tag2=5Fe(l:2), Ruc=[0 0 0]>
        """

        if M1._dh is M2._dh:
            self._dh: sisl.physics.Hamiltonian = M1._dh
        elif (M1._dh.Hk().toarray() == M2._dh.Hk().toarray()).all() and (
            M1._dh.Sk().toarray() == M2._dh.Sk().toarray()
        ).all():
            self._dh: sisl.physics.Hamiltonian = M1._dh
        else:
            raise Exception("Different Hamiltonians from the magnetic entities!")

        self.M1: MagneticEntity = M1
        self.M2: MagneticEntity = M2

        self.supercell_shift: NDArray = np.array(supercell_shift)

        # initialize simulation parameters
        self._Gij: list[NDArray] = []
        self._Gji: list[NDArray] = []
        self._Gij_tmp: list[NDArray] = []
        self._Gji_tmp: list[NDArray] = []

        self.energies: Union[None, NDArray] = None
        self.J_iso: Union[float, None] = None
        self.J: Union[NDArray, None] = None
        self.J_S: Union[NDArray, None] = None
        self.D: Union[NDArray, None] = None

        # pre calculate hidden unuseed properties
        # they are here so they are dumped to the self.__dict__ upon saving
        self.__SBS1 = self.M1.SBS
        self.__SBS2 = self.M2.SBS
        self.__SBI1 = self.M1._spin_box_indices
        self.__SBI2 = self.M2._spin_box_indices
        self.__tags = [self.M1.tag, self.M2.tag]
        self.__cell = self._dh.cell
        self.__supercell_shift_xyz = self.supercell_shift @ self.cell
        self.__xyz = np.array(
            [self.M1._xyz, self.M2._xyz + self.supercell_shift_xyz], dtype=object
        )
        self.__xyz_center = np.array(
            [self.M1.xyz_center, self.M2.xyz_center + self.supercell_shift_xyz]
        )
        self.__distance = np.linalg.norm(self.xyz_center[0] - self.xyz_center[1])
        self.__energies_meV = None
        self.__energies_mRy = None
        self.__J_meV = None
        self.__J_mRy = None
        self.__D_meV = None
        self.__D_mRy = None
        self.__J_S_meV = None
        self.__J_S_mRy = None
        self.__J_iso_meV = None
        self.__J_iso_mRy = None

        Pair.number_of_pairs += 1

    def __getstate__(self):
        state = self.__dict__.copy()
        state["M1"] = state["M1"].__getstate__()
        state["M2"] = state["M2"].__getstate__()

        return state

    def __setstate__(self, state):
        M1 = object.__new__(MagneticEntity)
        M1.__setstate__(state["M1"])
        state["M1"] = M1
        M2 = object.__new__(MagneticEntity)
        M2.__setstate__(state["M2"])
        state["M2"] = M2

        self.__dict__ = state

    def __eq__(self, value):
        if isinstance(value, Pair):
            if (
                np.allclose(self._dh.Hk().toarray(), value._dh.Hk().toarray())
                and np.allclose(self._dh.Sk().toarray(), value._dh.Sk().toarray())
                and self.M1 == value.M1
                and self.M2 == value.M2
                and np.allclose(self.supercell_shift, value.supercell_shift)
                and np.allclose(self._Gij, value._Gij)
                and np.allclose(self._Gji, value._Gji)
                and np.allclose(self._Gij_tmp, value._Gij_tmp)
                and np.allclose(self._Gji_tmp, value._Gji_tmp)
                and np.allclose(self.energies, value.energies)
                and np.allclose(self.J_iso, value.J_iso)
                and np.allclose(self.J, value.J)
                and np.allclose(self.J_S, value.J_S)
                and np.allclose(self.D, value.D)
            ):
                return True
            return False
        return False

    def __repr__(self) -> str:
        """String representation of the instance."""

        out = f"<grogupy.Pair tag1={self.tags[0]}, tag2={self.tags[1]}, Ruc={self.supercell_shift}>"

        return out

    @property
    def SBS1(self) -> int:
        """Spin box size of the first magnetic entity."""
        self.__SBS1 = self.M1.SBS
        return self.__SBS1

    @property
    def SBS2(self) -> int:
        """Spin box size of the second magnetic entity."""
        self.__SBS2 = self.M2.SBS
        return self.__SBS2

    @property
    def SBI1(self) -> NDArray:
        """Spin box indices of the first magnetic entity."""
        self.__SBI1 = self.M1._spin_box_indices
        return self.__SBI1

    @property
    def SBI2(self) -> NDArray:
        """Spin box indices of the second magnetic entity."""
        self.__SBI2 = self.M2._spin_box_indices
        return self.__SBI2

    @property
    def tags(self) -> list[str]:
        """Tags of the magnetic entities."""
        self.__tags = [self.M1.tag, self.M2.tag]
        return self.__tags

    @property
    def cell(self):
        """Unit cell of the system."""
        self.__cell = self._dh.cell
        return self.__cell

    @property
    def supercell_shift_xyz(self) -> NDArray:
        """Supercell shift in Angstrom."""
        self.__supercell_shift_xyz = self.supercell_shift @ self.cell
        return self.__supercell_shift_xyz

    @property
    def xyz(self) -> NDArray:
        """Coordinates of the magnetic entities."""
        self.__xyz = np.array(
            [self.M1.xyz, self.M2.xyz + self.supercell_shift_xyz], dtype=object
        )
        return self.__xyz

    @property
    def xyz_center(self) -> NDArray:
        """Center coordinates of the magnetic entities."""
        self.__xyz_center = np.array(
            [self.M1.xyz_center, self.M2.xyz_center + self.supercell_shift_xyz]
        )
        return self.__xyz_center

    @property
    def distance(self) -> float:
        """Distance of the magnetic entities."""
        self.__distance = np.linalg.norm(self.xyz_center[0] - self.xyz_center[1])
        return self.__distance

    @property
    def energies_meV(self) -> NDArray:
        """The energies, but in meV."""
        if self.energies is None:
            self.__energies_meV = None
        else:
            self.__energies_meV = self.energies * sisl.unit_convert("eV", "meV")
        return self.__energies_meV

    @property
    def energies_mRy(self) -> NDArray:
        """The energies, but in mRy."""
        if self.energies is None:
            self.__energies_mRy = None
        else:
            self.__energies_mRy = self.energies * sisl.unit_convert("eV", "mRy")
        return self.__energies_mRy

    @property
    def J_meV(self) -> NDArray:
        """The exchange tensor, but in meV."""
        if self.J is None:
            self.__J_meV = None
        else:
            self.__J_meV = self.J * sisl.unit_convert("eV", "meV")
        return self.__J_meV

    @property
    def J_mRy(self) -> NDArray:
        """The exchange tensor, but in mRy."""
        if self.J is None:
            self.__J_mRy = None
        else:
            self.__J_mRy = self.J * sisl.unit_convert("eV", "mRy")
        return self.__J_mRy

    @property
    def D_meV(self) -> NDArray:
        """The DM vector, but in meV."""
        if self.D is None:
            self.__D_meV = None
        else:
            self.__D_meV = self.D * sisl.unit_convert("eV", "meV")
        return self.__D_meV

    @property
    def D_mRy(self) -> NDArray:
        """The DM vector, but in mRy."""
        if self.D is None:
            self.__D_mRy = None
        else:
            self.__D_mRy = self.D * sisl.unit_convert("eV", "mRy")
        return self.__D_mRy

    @property
    def J_S_meV(self) -> NDArray:
        """The symmetric part of the exchange tensor, but in meV."""
        if self.J_S is None:
            self.__J_S_meV = None
        else:
            self.__J_S_meV = self.J_S * sisl.unit_convert("eV", "meV")
        return self.__J_S_meV

    @property
    def J_S_mRy(self) -> NDArray:
        """The symmetric part of the exchange tensor, but in mRy."""
        if self.J_S is None:
            self.__J_S_mRy = None
        else:
            self.__J_S_mRy = self.J_S * sisl.unit_convert("eV", "mRy")
        return self.__J_S_mRy

    @property
    def J_iso_meV(self) -> NDArray:
        """The isotropic exchange, but in meV."""
        if self.J_iso is None:
            self.__J_iso_meV = None
        else:
            self.__J_iso_meV = self.J_iso * sisl.unit_convert("eV", "meV")
        return self.__J_iso_meV

    @property
    def J_iso_mRy(self) -> NDArray:
        """The isotropic exchange, but in mRy."""
        if self.J_iso is None:
            self.__J_iso_mRy = None
        else:
            self.__J_iso_mRy = self.J_iso * sisl.unit_convert("eV", "mRy")
        return self.__J_iso_mRy

    def reset(self) -> None:
        """Resets the simulation results of the Pair.

        Does not reset the underlying Magnetic Entity instances.
        """

        self._Gij: list[NDArray] = []
        self._Gji: list[NDArray] = []
        self._Gij_tmp: list[NDArray] = []
        self._Gji_tmp: list[NDArray] = []
        self.energies: Union[None, NDArray] = None

        self.J_iso: Union[float, None] = None
        self.J: Union[NDArray, None] = None
        self.J_S: Union[NDArray, None] = None
        self.D: Union[NDArray, None] = None

    def calculate_energies(self, weights: NDArray) -> None:
        """Calculates the energies of the infinitesimal rotations.

        It uses the instance properties to calculate the energies and
        dumps the results to the `energies` property.

        Parameters
        ----------
        weights: NDArray
            The weights of the energy contour integral
        """

        energies: list[list[float]] = []
        for i, (Gij, Gji) in enumerate(zip(self._Gij, self._Gji)):
            storage: list = []
            # iterate over the first order local perturbations in all possible orientations for the two sites
            # actually all possible orientations without the orientation for the off-diagonal anisotropy
            # that is why we only take the first two of each Vu1
            for Vui in self.M1._Vu1[i][:2]:
                for Vuj in self.M2._Vu1[i][:2]:
                    storage.append(interaction_energy(Vui, Vuj, Gij, Gji, weights))
            # fill up the pairs dictionary with the energies
            energies.append(storage)

        # convert to np array
        self.energies: NDArray = np.array(energies)
        # call these so they are updated
        self.energies_meV
        self.energies_mRy

    def calculate_exchange_tensor(self) -> None:
        """Calculates the exchange tensor from the energies.

        It uses the instance properties to calculate the exchange tensor
        and its different representations and dumps them to the `J`, `J_iso`,
        `J_S` and `D` properties.

        """

        J_iso, J_S, D, J = calculate_exchange_tensor(self.energies)
        self.J: NDArray = J
        self.J_S: NDArray = J_S
        self.J_iso: float = J_iso
        self.D: NDArray = D
        # call these so they are updated
        self.J_meV
        self.J_mRy
        self.J_S_meV
        self.J_S_mRy
        self.J_iso_meV
        self.J_iso_mRy
        self.D_meV
        self.D_mRy

    def fit_exchange_tensor(self, ref_xcf: list[dict]) -> None:
        """Fits the exchange tensor to the energies.

        It uses a fitting method to calculate the exchange tensor from the
        reference directions and its different representations and dumps
        them to the `J`, `J_iso`, `J_S` and `D` properties.

        Parameters
        ----------
        ref_xcf: list[dict]
            The reference directions containing the orientation and perpendicular directions
        """

        J_iso, J_S, D, J = fit_exchange_tensor(self.energies, ref_xcf)
        self.J: NDArray = J
        self.J_S: NDArray = J_S
        self.J_iso: float = J_iso
        self.D: NDArray = D
        # call these so they are updated
        self.J_meV
        self.J_mRy
        self.J_S_meV
        self.J_S_mRy
        self.J_iso_meV
        self.J_iso_mRy
        self.D_meV
        self.D_mRy

    def add_G_tmp(self, i: int, Gk: NDArray, k: NDArray, weight: float) -> None:
        """Adds the calculated Greens function to the temporary Greens function.

        It is used in the parallel solution of the Hamiltonian inversions. Now the
        supercell shift is needed, because it introduces a phase shift to the Greens
        function.

        Parameters
        ----------
        i: int
            The index of the `ref_xcf_orientation`
        Gk: NDArray
            The Greens function projection on a specific k-point
        k: NDArray
            It is the supercell shift of the second magnetic entity
        weight: float
            The weight of the k-point
        """

        # add phase shift based on the cell difference
        phase: NDArray = np.exp(1j * 2 * np.pi * k @ self.supercell_shift.T)

        # store the Greens function slice of the magnetic entities
        self._Gij_tmp[i] += onsite_projection(Gk, self.SBI1, self.SBI2) * phase * weight
        self._Gji_tmp[i] += onsite_projection(Gk, self.SBI2, self.SBI1) / phase * weight

    def copy(self):
        """Returns the deepcopy of the instance.

        Returns
        -------
        Pair
            The copied instance.
        """

        return copy.deepcopy(self)


if __name__ == "__main__":
    pass
