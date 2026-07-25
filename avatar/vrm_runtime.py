"""
avatar/vrm_runtime.py
=====================
Carregador e runtime para modelos VRM.

Responsabilidades:
  - Parsear arquivo VRM (0.0 / 1.0)
  - Carregar malhas, esqueleto, blend shapes
  - Fornecer API para animação e expressão
  - Gerenciar ciclo de vida (load/unload)

Dependências:
  - trimesh: Parser 3D genérico
  - numpy: Álgebra linear
"""

import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json

try:
    import trimesh
    import numpy as np
except ImportError as e:
    raise ImportError(
        "VRMRuntime requer 'trimesh' e 'numpy'.\n"
        "Instale com: pip install trimesh numpy"
    ) from e

from core.logger import setup_logger

logger = setup_logger("vrm_runtime")


@dataclass
class VRMMetadata:
    """Metadados do modelo VRM."""

    title: str = ""
    version: str = ""
    author: str = ""
    contact: str = ""
    reference: str = ""
    texture_count: int = 0
    material_count: int = 0
    mesh_count: int = 0
    bone_count: int = 0
    blend_shape_count: int = 0

    def __str__(self) -> str:
        return f"VRM({self.title} v{self.version} by {self.author})"


class VRMBlendShape:
    """Representa um Blend Shape (Shape Key) do VRM."""

    def __init__(self, name: str, index: int, weight: float = 0.0):
        self.name = name
        self.index = index
        self.weight = weight  # 0.0-1.0
        self.target_vertex_indices: List[int] = []
        self.target_positions: np.ndarray = np.array([])

    def set_weight(self, weight: float) -> None:
        """Define peso do blend shape (0.0-1.0)."""
        self.weight = max(0.0, min(1.0, weight))

    def apply(self, vertices: np.ndarray) -> np.ndarray:
        """
        Aplica o blend shape aos vértices.

        Args:
            vertices: Array de vértices [N, 3]

        Returns:
            Vértices com blend shape aplicado
        """
        if self.weight == 0.0 or len(self.target_vertex_indices) == 0:
            return vertices

        result = vertices.copy()
        for i, vertex_idx in enumerate(self.target_vertex_indices):
            if vertex_idx < len(result) and i < len(self.target_positions):
                result[vertex_idx] += self.target_positions[i] * self.weight

        return result


class VRMMesh:
    """Representa uma malha dentro do VRM."""

    def __init__(self, name: str):
        self.name = name
        self.vertices: np.ndarray = np.array([])
        self.faces: np.ndarray = np.array([])
        self.normals: np.ndarray = np.array([])
        self.uv_coords: np.ndarray = np.array([])
        self.material_index: int = 0
        self.bones: List[str] = []
        self.weights: List[np.ndarray] = []


class VRMRuntime:
    """Runtime VRM — carregador, renderizador e animador."""

    def __init__(self, vrm_path: str):
        """
        Inicializa VRMRuntime com arquivo VRM.

        Args:
            vrm_path: Caminho para arquivo .vrm

        Raises:
            FileNotFoundError: Se arquivo não existe
            ValueError: Se arquivo não é VRM válido
        """
        if not os.path.exists(vrm_path):
            raise FileNotFoundError(f"Arquivo VRM não encontrado: {vrm_path}")

        self.vrm_path = vrm_path
        self.metadata = VRMMetadata()
        self.meshes: Dict[str, VRMMesh] = {}
        self.blend_shapes: Dict[str, VRMBlendShape] = {}
        self.skeleton: Dict[str, Dict] = {}
        self.materials: List[Dict] = []
        self.textures: Dict[str, np.ndarray] = {}

        self.is_loaded = False
        self._load_vrm()

    def _load_vrm(self) -> None:
        """
        Carrega arquivo VRM usando trimesh.

        VRM é essencialmente um glTF com extensões.
        trimesh consegue parsear a maioria dos VRMs.
        """
        try:
            logger.info(f"Carregando VRM: {self.vrm_path}")

            # Carrega via trimesh
            scene = trimesh.load(self.vrm_path, process=False, skip_materials=False)

            if isinstance(scene, trimesh.Scene):
                # Múltiplas malhas
                for name, mesh in scene.geometry.items():
                    self._add_mesh_from_trimesh(name, mesh)
                logger.info(f"Carregadas {len(self.meshes)} malhas da cena")
            else:
                # Malha única
                self._add_mesh_from_trimesh("default", scene)
                logger.info("Carregada malha única")

            self._parse_metadata()
            self.is_loaded = True
            logger.info(f"VRM carregado com sucesso: {self.metadata}")

        except Exception as e:
            logger.error(f"Erro ao carregar VRM: {e}")
            raise ValueError(f"VRM inválido ou não suportado: {self.vrm_path}") from e

    def _add_mesh_from_trimesh(self, name: str, mesh: trimesh.Trimesh) -> None:
        """Adiciona malha do trimesh ao runtime."""
        vrm_mesh = VRMMesh(name)
        vrm_mesh.vertices = mesh.vertices.copy()
        vrm_mesh.faces = mesh.faces.copy()
        vrm_mesh.normals = mesh.vertex_normals.copy()

        self.meshes[name] = vrm_mesh

    def _parse_metadata(self) -> None:
        """Extrai metadados do VRM (nome, autor, versão)."""
        try:
            # Tenta ler glTF extras
            vrm_file = trimesh.load(self.vrm_path, process=False)

            # Simples extraction
            self.metadata.title = os.path.basename(self.vrm_path).replace(".vrm", "")
            self.metadata.mesh_count = len(self.meshes)
            self.metadata.version = "0.0"  # Default, poderia parsear do arquivo

        except Exception as e:
            logger.warning(f"Erro ao parsear metadados: {e}")

    def get_mesh(self, name: str) -> Optional[VRMMesh]:
        """Obtém malha pelo nome."""
        return self.meshes.get(name)

    def get_all_meshes(self) -> Dict[str, VRMMesh]:
        """Retorna todas as malhas."""
        return self.meshes.copy()

    def add_blend_shape(self, name: str) -> VRMBlendShape:
        """
        Cria novo blend shape.

        Args:
            name: Nome do blend shape (ex: "a", "i", "u", "e", "o")

        Returns:
            VRMBlendShape criado
        """
        blend_shape = VRMBlendShape(name, len(self.blend_shapes))
        self.blend_shapes[name] = blend_shape
        return blend_shape

    def set_blend_shape_weight(self, name: str, weight: float) -> bool:
        """
        Define peso de um blend shape.

        Args:
            name: Nome do blend shape
            weight: Peso (0.0-1.0)

        Returns:
            True se sucesso, False se blend shape não existe
        """
        if name not in self.blend_shapes:
            logger.warning(f"Blend shape não encontrado: {name}")
            return False

        self.blend_shapes[name].set_weight(weight)
        return True

    def get_blend_shape(self, name: str) -> Optional[VRMBlendShape]:
        """Obtém blend shape pelo nome."""
        return self.blend_shapes.get(name)

    def get_all_blend_shapes(self) -> Dict[str, VRMBlendShape]:
        """Retorna todos os blend shapes com seus pesos atuais."""
        return {name: bs for name, bs in self.blend_shapes.items()}

    def get_skeleton(self) -> Dict[str, Dict]:
        """Retorna estrutura do esqueleto."""
        return self.skeleton.copy()

    def get_bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Retorna bounding box do modelo.

        Returns:
            Tupla (min, max) em coordenadas 3D
        """
        if not self.meshes:
            return np.array([0, 0, 0]), np.array([1, 1, 1])

        all_vertices = np.vstack([mesh.vertices for mesh in self.meshes.values()])
        return all_vertices.min(axis=0), all_vertices.max(axis=0)

    def get_center(self) -> np.ndarray:
        """Retorna centro do modelo."""
        min_bounds, max_bounds = self.get_bounds()
        return (min_bounds + max_bounds) / 2.0

    def scale(self, factor: float) -> None:
        """
        Escala o modelo.

        Args:
            factor: Fator de escala (2.0 = 2x maior)
        """
        for mesh in self.meshes.values():
            mesh.vertices *= factor
            mesh.normals /= factor  # Normaliza novamente

        logger.info(f"Modelo escalado por {factor}x")

    def translate(self, offset: np.ndarray) -> None:
        """
        Translada o modelo.

        Args:
            offset: Deslocamento [x, y, z]
        """
        offset = np.array(offset)
        for mesh in self.meshes.values():
            mesh.vertices += offset

        logger.info(f"Modelo transladado por {offset}")

    def rotate(self, angle_degrees: float, axis: str = "y") -> None:
        """
        Rotaciona o modelo.

        Args:
            angle_degrees: Ângulo em graus
            axis: Eixo ("x", "y" ou "z")
        """
        angle_rad = np.radians(angle_degrees)

        if axis.lower() == "x":
            rot_matrix = np.array([
                [1, 0, 0],
                [0, np.cos(angle_rad), -np.sin(angle_rad)],
                [0, np.sin(angle_rad), np.cos(angle_rad)],
            ])
        elif axis.lower() == "y":
            rot_matrix = np.array([
                [np.cos(angle_rad), 0, np.sin(angle_rad)],
                [0, 1, 0],
                [-np.sin(angle_rad), 0, np.cos(angle_rad)],
            ])
        elif axis.lower() == "z":
            rot_matrix = np.array([
                [np.cos(angle_rad), -np.sin(angle_rad), 0],
                [np.sin(angle_rad), np.cos(angle_rad), 0],
                [0, 0, 1],
            ])
        else:
            logger.warning(f"Eixo desconhecido: {axis}")
            return

        for mesh in self.meshes.values():
            mesh.vertices = mesh.vertices @ rot_matrix.T
            mesh.normals = mesh.normals @ rot_matrix.T

        logger.info(f"Modelo rotacionado {angle_degrees}° no eixo {axis}")

    def unload(self) -> None:
        """Libera recursos do VRM."""
        self.meshes.clear()
        self.blend_shapes.clear()
        self.skeleton.clear()
        self.materials.clear()
        self.textures.clear()
        self.is_loaded = False
        logger.info(f"VRM descarregado: {self.vrm_path}")

    def __del__(self):
        """Cleanup automático."""
        if self.is_loaded:
            self.unload()
