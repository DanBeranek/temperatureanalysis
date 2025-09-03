from __future__ import annotations

from typing import TYPE_CHECKING

from temperatureanalysis.fea.analysis.finite_elements.finite_element import FiniteElement

if TYPE_CHECKING:
    from temperatureanalysis.fea.pre.material import Material
    from temperatureanalysis.fea.analysis.node import Node


class Tri6(FiniteElement):
    """
    Represents a three-node quadratic triangular finite element (Tri6).
    """
    def __init__(
        self,
        index: int,
        tag: str,
        nodes: list[Node],
        material: Material
    ) -> None:
        """
        Initialize the Tri6 element.

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
            n_integration_points=6
        )
        raise NotImplementedError(
            "Tri6 elements are not yet implemented. "
            "Please use Tri3 elements for now."
        )
