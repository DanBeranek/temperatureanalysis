from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from temperatureanalysis.analysis.finite_elements.finite_element import FiniteElement
import temperatureanalysis.analysis.gauss as gauss

if TYPE_CHECKING:
    import numpy.typing as npt
    from temperatureanalysis.pre.material import Material
    from temperatureanalysis.analysis.node import Node


class Quad4(FiniteElement):
    """
    Represents a four-node linear quadrilateral finite element (Quad4).
    """
    def __init__(
        self,
        index: int,
        tag: str,
        nodes: list[Node],
        material: Material
    ) -> None:
        """
        Initialize the Quad4 element.

        Args:
            index: Element index.
            tag: Element tag.
            nodes: List of nodes that form the element.
            material: The material associated with the element.
        """
        super().__init__(
            index=index,
            tag=tag,
            nodes=nodes,
            material=material,
            n_integration_points=4
        )
        raise NotImplementedError(
            "Quad4 elements are not yet implemented. "
            "Please use Tri3 elements for now."
        )
