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
"""magnetic entity

_extended_summary_
"""

import copy
from typing import TYPE_CHECKING, Union

from numpy.typing import NDArray

if TYPE_CHECKING:
    from .hamiltonian import Hamiltonian

import numpy as np
import sisl

from .. import __version__
from .._core.core import onsite_projection
from .._core.utilities import arrays_lists_equal, arrays_None_equal
from .utilities import (
    blow_up_orbindx,
    calculate_anisotropy_tensor,
    fit_anisotropy_tensor,
    interaction_energy,
    parse_magnetic_entity,
    second_order_energy,
)


class MagneticEntity:
    """This class contains the data and the methods related to the magnetic entities.

    It sets up the instance based on the indexing of the Hamiltonian by the ``atom``,
    ``l`` and orbital (``orb``) parameters.

    There are four possible input types:
    1. Cluster: a list of atoms
    2. AtomShell: one atom and a list of shells indexed in the atom or
    a list of atoms and a list of lists containing the shells
    3. AtomOrbital: one atom and a list of orbitals indexed in the atom or
    a list of atoms and a list of lists containing the orbitals
    4. Orbitals: a list of orbitals  indexed in the Hamiltonian

    Parameters
    ----------
    infile: Union[str, tuple[Union[sisl.physics.Hamiltonian, Hamiltonian], sisl.physics.DensityMatrix]]
        Either the path to the .fdf file or a tuple of sisl or grogupy hamiltonian and a sisl density matrix
    atom: Union[None, int, list[int]], optional
        Defining atom (or atoms) in the unit cell forming the magnetic entity, by default None
    l: Union[None, int, list[int], list[list[int]]], optional
        Defining the angular momentum channel, by default None
    orb: Union[None, int, list[int], list[list[int]]], optional
            Defining the orbital index in the Hamiltonian or on the atom, by default None

    Examples
    --------
    Creating a magnetic entity can be done by giving the Hamiltonian from the
    DFT calculation and somehow specifying the corresponding atoms and orbitals.

    The following examples show you how to create magnetic entities in the
    **Fe3GeTe2** system. You can compare the tags of the ``MagneticEntity``
    to the input parameters, to understand how to build the magnetic entity,
    that suits your needs.

    >>> fdf_path = "/Users/danielpozsar/Downloads/Fe3GeTe2/Fe3GeTe2.fdf"

    To define a Cluster of atoms use a dictionary that only contains atoms.

    >>> magnetic_entity = MagneticEntity(fdf_path, atom=[3,4,5])
    >>> print(magnetic_entity.tag)
    3Fe(l:All)--4Fe(l:All)--5Fe(l:All)

    To define a magnetic entity with a single atom, but with specific
    shells use both the ``atom`` and ``l`` key in the dictionary.

    >>> magnetic_entity = MagneticEntity(fdf_path, atom=5, l=[[1,2,3]])
    >>> print(magnetic_entity.tag)
    5Fe(l:1-2-3)

    Or you can define multiple atoms with different shells:

    >>> magnetic_entity = MagneticEntity(fdf_path, atom=[4,5], l=[[1],[1,2,3]])
    >>> print(magnetic_entity.tag)
    4Fe(l:1)--5Fe(l:1-2-3)

    To define a magnetic entity with a single atom, but with specific
    orbitals use both the ``atom`` and ``orb`` key in the dictionary.
    Be aware that these orbitals are indexed inside the atom, not in the
    total Hamiltonian.

    >>> magnetic_entity = MagneticEntity(fdf_path, atom=5, orb=[[1,2,3,4,5,6,7,8,9,10]])
    >>> print(magnetic_entity.tag)
    5Fe(o:1-2-3-4-5-6-7-8-9-10)

    Or you can define multiple atoms with different orbitals:

    >>> magnetic_entity = MagneticEntity(fdf_path, atom=[4,5], orb=[[1],[1,2,3,4,5,6,7,8,9,10]])
    >>> print(magnetic_entity.tag)
    4Fe(o:1)--5Fe(o:1-2-3-4-5-6-7-8-9-10)

    And finally you can use only the ``orb`` key to directly index the
    orbitals from the Hamiltonian.

    >>> magnetic_entity = MagneticEntity(fdf_path, orb=[1,10,30,40,50])
    >>> print(magnetic_entity.tag)
    0Te(o:1-10)--2Ge(o:4)--3Fe(o:1-11)


    Methods
    -------
    calculate_energies(weights) :
        Calculates the energies of the infinitesimal rotations.
    calculate_anisotropy() :
        Calculates the anisotropy matrix and the consistency from the energies.
    to_dict(all) :
        Returns the instance data as a dictionary.
    add_G_tmp(i, Gk, weight) :
        Adds the calculated Greens function to the temporary Greens function.
    copy() :
        Return a copy of this MagneticEntity

    Attributes
    ----------
    _orbital_box_indices : NDArray
        The ORBITAL BOX indices
    _atom : NDArray
        The list of atoms in the magnetic entity
    _l : list[list[Union[None, int]]]
        The list of l in the magnetic entity, None if it is incomplete
    _spin_box_indices : NDArray
        The SPIN BOX indices
    SBS : int
        Length of the SPIN BOX indices
    _xyz : NDArray
        The coordinates of the magnetic entity (it can consist of many atoms)
    _xyz_center : NDArray
        The center of coordinates for the magnetic entity
    _tag : str
        The description of the magnetic entity
    _Vu1 : list[list[float]]
        The list of the first order rotations
    _Vu2 : list[list[float]]
        The list of the second order rotations
    _Gii : list[NDArray]
        The list of the projected Greens functions
    energies : Union[None, NDArray]
        The calculated energies for each direction
    K : Union[NDArray, None]
        The magnetic anisotropy, by default None
    K_consistency : Union[float, None]
        Consistency check on the diagonal K elements, by default None
    """

    number_of_entities: int = 0

    def __init__(
        self,
        infile: Union[
            str,
            tuple[
                Union[sisl.physics.Hamiltonian, "Hamiltonian"],
                sisl.physics.DensityMatrix,
            ],
        ],
        atom: Union[None, int, list[int]] = None,
        l: Union[None, int, list[int], list[list[int]]] = None,
        orb: Union[None, int, list[int], list[list[int]]] = None,
    ) -> None:
        """Initialize the magnetic entity."""

        if isinstance(infile, str):
            # get sisl sile
            sile = sisl.io.get_sile(infile)
            # load density and hamiltonian
            self._dh: sisl.physics.Hamiltonian = sile.read_hamiltonian()
            self._ds: sisl.physics.DensityMatrix = sile.read_density_matrix()
            self.infile: str = infile
        elif isinstance(infile, tuple):
            self._dh: sisl.physics.Hamiltonian = infile[0]
            self._ds: sisl.physics.DensityMatrix = infile[1]
            self.infile: str = "Unknown!"
        else:
            raise Exception("Cannot setup without path or sisl objects!")
        atom, l, orbital, tag = parse_magnetic_entity(self._dh, atom, l, orb)
        self._atom: NDArray = np.array([atom]).flatten()
        self._l = l
        self._orbital_box_indices: NDArray = np.array(orbital).flatten()
        self._tags = tag
        self._total_mulliken: NDArray = self._ds.mulliken()[
            :, self._dh.a2o(self._atom, all=True)
        ]
        self._local_mulliken: NDArray = self._ds.mulliken()[
            :, self._orbital_box_indices
        ]

        self._spin_box_indices: NDArray = blow_up_orbindx(self._orbital_box_indices)
        self._xyz: NDArray = np.array([self._dh.xyz[i] for i in self._atom])

        # initialize simulation parameters
        self._Vu1: list[list[NDArray]] = []
        self._Vu2: list[list[NDArray]] = []
        self._Gii: list[NDArray] = []
        self._Gii_tmp: list[NDArray] = []

        self.energies: Union[None, NDArray] = None
        self.K: Union[None, NDArray] = None
        self.K_consistency: Union[None, float] = None

        # pre calculate hidden unuseed properties
        # they are here so they are dumped to the self.__dict__ upon saving
        self.__tag = "--".join(self._tags)
        self.__SBS = len(self._spin_box_indices)
        self.__xyz_center = self._xyz.mean(axis=0)
        self.__total_Q = self._total_mulliken[0].sum()
        self.__total_Sx = self._total_mulliken[1].sum()
        self.__total_Sy = self._total_mulliken[2].sum()
        self.__total_Sz = self._total_mulliken[3].sum()
        self.__local_Q = self._local_mulliken[0].sum()
        self.__local_Sx = self._local_mulliken[1].sum()
        self.__local_Sy = self._local_mulliken[2].sum()
        self.__local_Sz = self._local_mulliken[3].sum()
        self.__energies_meV = None
        self.__energies_mRy = None
        self.__K_meV = None
        self.__K_mRy = None
        self.__K_consistency_meV = None
        self.__K_consistency_mRy = None

        MagneticEntity.number_of_entities += 1

    def __getstate__(self):
        return self.__dict__.copy()

    def __setstate__(self, state):
        self.__dict__ = state

    def __add__(self, value):
        if not isinstance(value, MagneticEntity):
            raise Exception("Only MagneticEntity instances can be added!")

        # do not change the current instance
        new = self.copy()
        # reset the values that does not make sense for a new magnetic entity
        new.reset()
        # update out instance
        # accept both kinds of hamiltonian
        if not arrays_lists_equal(new._dh.Hk().toarray(), value._dh.Hk().toarray()):
            raise Exception("The sisl Hamiltonians are not the same!")
        if not arrays_lists_equal(new._dh.Sk().toarray(), value._dh.Sk().toarray()):
            raise Exception("The sisl Overlap matrices are not the same!")

        new._atom = np.hstack((new._atom, value._atom))
        new._l = new._l + value._l
        new._orbital_box_indices = np.hstack(
            (new._orbital_box_indices, value._orbital_box_indices)
        )
        new._tags = new._tags + value._tags

        new._spin_box_indices = blow_up_orbindx(new._orbital_box_indices)
        new._xyz = np.vstack((new._xyz, value._xyz))

        return new

    def __eq__(self, value):
        if isinstance(value, MagneticEntity):
            # if the IDs are identical, skip comaprison
            if id(self) == id(value):
                return True

            if not arrays_lists_equal(
                self._dh.Hk().toarray(), value._dh.Hk().toarray()
            ):
                return False
            if not arrays_lists_equal(
                self._dh.Sk().toarray(), value._dh.Sk().toarray()
            ):
                return False
            if not arrays_lists_equal(
                self._ds.Dk().toarray(), value._ds.Dk().toarray()
            ):
                return False
            if not arrays_lists_equal(
                self._ds.Sk().toarray(), value._ds.Sk().toarray()
            ):
                return False
            if not self.infile == value.infile:
                return False
            if not arrays_lists_equal(self._atom, value._atom):
                return False
            if not self._l == value._l:
                return False
            if not arrays_lists_equal(
                self._orbital_box_indices, value._orbital_box_indices
            ):
                return False
            if not self._tags == value._tags:
                return False
            if not arrays_lists_equal(self._total_mulliken, value._total_mulliken):
                return False
            if not arrays_lists_equal(self._local_mulliken, value._local_mulliken):
                return False
            if not arrays_lists_equal(self._spin_box_indices, value._spin_box_indices):
                return False
            if not arrays_lists_equal(self._xyz, value._xyz):
                return False
            if not arrays_lists_equal(self._Vu1, value._Vu1):
                return False
            if not arrays_lists_equal(self._Vu2, value._Vu2):
                return False
            if not arrays_lists_equal(self._Gii, value._Gii):
                return False
            if not arrays_lists_equal(self._Gii_tmp, value._Gii_tmp):
                return False
            if not arrays_None_equal(self.energies, value.energies):
                return False
            if not arrays_None_equal(self.K, value.K):
                return False
            # Checking K_consistency separately
            # if both are None, then pass and no other check is perfomred because of elif
            if self.K_consistency is None and value.K_consistency is None:
                pass
            # if either one is None, but the other is not, then return false
            elif self.K_consistency is not None and value.K_consistency is None:
                return False
            elif self.K_consistency is None and value.K_consistency is not None:
                return False
            # If neither of them is None, compare them
            elif not np.isclose(self.K_consistency, value.K_consistency):
                return False
            return True
        else:
            return False

    def __repr__(self) -> str:
        """String representation of the instance."""

        out = f"<grogupy.MagneticEntity tag={self.tag}, SBS={self.SBS}>"

        return out

    @property
    def tag(self):
        """The description of the magnetic entity"""
        self.__tag = "--".join(self._tags)

        return self.__tag

    @property
    def SBS(self) -> int:
        """The spin box size of the magnetic entity"""
        self.__SBS = len(self._spin_box_indices)

        return self.__SBS

    @property
    def xyz_center(self) -> NDArray:
        """The mean of the position of the atoms that are in the magnetic entity."""
        self.__xyz_center = self._xyz.mean(axis=0)

        return self.__xyz_center

    @property
    def total_Q(self) -> NDArray:
        """The total charge of the atom or the atoms of magnetic entity."""
        self.__total_Q = self._total_mulliken[0].sum()

        return self.__total_Q

    @property
    def total_Sx(self) -> NDArray:
        """The non-collinear Sx of the atom or the atoms of the magnetic entity."""
        self.__total_Sx = self._total_mulliken[1].sum()

        return self.__total_Sx

    @property
    def total_Sy(self) -> NDArray:
        """The non-collinear Sy of the atom or the atoms of the magnetic entity."""
        self.__total_Sy = self._total_mulliken[2].sum()

        return self.__total_Sy

    @property
    def total_Sz(self) -> NDArray:
        """The non-collinear Sz of the atom or the atoms of the magnetic entity."""
        self.__total_Sz = self._total_mulliken[3].sum()

        return self.__total_Sz

    @property
    def local_Q(self) -> NDArray:
        """The charge of the magnetic entity."""
        self.__local_Q = self._local_mulliken[0].sum()

        return self.__local_Q

    @property
    def local_Sx(self) -> NDArray:
        """The non-collinear Sx of the magnetic entity."""
        self.__local_Sx = self._local_mulliken[1].sum()

        return self.__local_Sx

    @property
    def local_Sy(self) -> NDArray:
        """The non-collinear Sy of the magnetic entity."""
        self.__local_Sy = self._local_mulliken[2].sum()

        return self.__local_Sy

    @property
    def local_Sz(self) -> NDArray:
        """The non-collinear Sz of the magnetic entity."""
        self.__local_Sz = self._local_mulliken[3].sum()

        return self.__local_Sz

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
    def K_meV(self) -> NDArray:
        """The anisotropy tensor, but in meV."""
        if self.K is None:
            self.__K_meV = None
        else:
            self.__K_meV = self.K * sisl.unit_convert("eV", "meV")
        return self.__K_meV

    @property
    def K_mRy(self) -> NDArray:
        """The anisotropy tensor, but in mRy."""
        if self.K is None:
            self.__K_mRy = None
        else:
            self.__K_mRy = self.K * sisl.unit_convert("eV", "mRy")
        return self.__K_mRy

    @property
    def K_consistency_meV(self) -> NDArray:
        """The consistency check, but in meV."""
        if self.K_consistency is None:
            self.__K_consistency_meV = None
        else:
            self.__K_consistency_meV = self.K_consistency * sisl.unit_convert(
                "eV", "meV"
            )
        return self.__K_consistency_meV

    @property
    def K_consistency_mRy(self) -> NDArray:
        """The consistency check, but in mRy."""
        if self.K_consistency is None:
            self.__K_consistency_mRy = None
        else:
            self.__K_consistency_mRy = self.K_consistency * sisl.unit_convert(
                "eV", "mRy"
            )
        return self.__K_consistency_mRy

    def reset(self) -> None:
        """Resets the simulation results."""

        self._Vu1: list[list[NDArray]] = []
        self._Vu2: list[list[NDArray]] = []
        self._Gii: list[NDArray] = []
        self._Gii_tmp: list[NDArray] = []
        self.energies: list[NDArray] = []
        self.K: Union[None, NDArray] = None
        self.K_consistency: Union[None, float] = None

    def add_G_tmp(self, i: int, Gk: NDArray, weight: float) -> None:
        """Adds the calculated Greens function to the temporary Greens function.

        It is used in the parallel solution of the Hamiltonian inversions.

        Parameters
        ----------
        i: int
            The index of the `ref_xcf_orientation`
        Gk: NDArray
            The Greens function projection on a specific k-point
        weight: float
            The weight of the k-point
        """
        self._Gii_tmp[i] += (
            onsite_projection(Gk, self._spin_box_indices, self._spin_box_indices)
            * weight
        )

    def calculate_energies(self, weights: NDArray, matlabmode: bool = False) -> None:
        """Calculates the energies of the infinitesimal rotations.

        It uses the instance properties to calculate the energies and
        dumps the results to the ``energies`` property.

        Parameters
        ----------
        weights : NDArray
            The weights of the energy contour integral
        matlabmode : bool, optional
            Wether to use a linear combination of the two perpendicular
            orientation, by default False
        """

        energies: list[list[float]] = []
        for i, Gii in enumerate(self._Gii):
            storage: list[float] = []
            # iterate over the first and second order local perturbations
            V1 = self._Vu1[i]
            V2 = self._Vu2[i]

            # fill up the magnetic entities dictionary with the energies
            storage.append(second_order_energy(V1[0], V2[0], Gii, weights))
            storage.append(interaction_energy(V1[0], V1[1], Gii, Gii, weights))
            storage.append(interaction_energy(V1[1], V1[0], Gii, Gii, weights))
            storage.append(second_order_energy(V1[1], V2[1], Gii, weights))
            if matlabmode:
                storage.append(second_order_energy(V1[2], V2[2], Gii, weights))
            energies.append(storage)

        # convert to array
        self.energies: NDArray = np.array(energies)
        # call these so they are updated
        self.energies_meV
        self.energies_mRy

    def calculate_anisotropy(self) -> None:
        """Calculates the anisotropy matrix and the consistency from the energies.

        It uses the instance properties to calculate the anisotropy matrix and the
        consistency and dumps them to the `K`, `K_consistency` properties.

        """

        K, K_consistency = calculate_anisotropy_tensor(self.energies)
        self.K: NDArray = K
        self.K_consistency: float = K_consistency
        # call these so they are updated
        self.K_meV
        self.K_mRy
        self.K_consistency_meV
        self.K_consistency_mRy

    def fit_anisotropy_tensor(self, ref_xcf: list[dict]) -> None:
        """Fits the anisotropy tensor to the energies.

        It uses a fitting method to calculate the anisotropy tensor from the
        reference directions and its different representations and dumps
        them to the ``K`` property. It writes ``None`` to the ``K_consistency``
        property.

        Parameters
        ----------
        ref_xcf: list[dict]
            The reference directions containing the orientation and perpendicular directions
        """

        K = fit_anisotropy_tensor(self.energies, ref_xcf)
        self.K: NDArray = K
        # it is not relevant with this method
        self.K_consistency: Union[float, None] = None
        # call these so they are updated
        self.K_meV
        self.K_mRy
        self.K_consistency_meV
        self.K_consistency_mRy

    def copy(self):
        """Returns the deepcopy of the instance.

        Returns
        -------
        MagneticEntity
            The copied instance.
        """

        return copy.deepcopy(self)


if __name__ == "__main__":
    pass
