from __future__ import annotations

from typing import TYPE_CHECKING

from temperatureanalysis.fea.analysis.finite_elements.finite_element import FiniteElement

if TYPE_CHECKING:
    from temperatureanalysis.fea.pre.material import Material
    from temperatureanalysis.fea.analysis.node import Node


class Quad8(FiniteElement):
    """
    Represents a four-node quadratic quadrilateral finite element (Quad8).
    """
    def __init__(
        self,
        index: int,
        tag: str,
        nodes: list[Node],
        material: Material
    ) -> None:
        """
        Initialize the Quad8 element.

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
            n_integration_points=8
        )
        raise NotImplementedError(
            "Tri6 elements are not yet implemented. "
            "Please use Quad8 elements for now."
        )
