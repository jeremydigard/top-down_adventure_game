from constants import TILE_SIZE

type Tile = int
type Pixel = float
type PixelPosition = tuple[Pixel, Pixel]
type TilePosition = tuple[Tile, Tile]
type TileBounds = tuple[Tile, Tile]
type MeshIndex = int
type MeshPosition = tuple[MeshIndex, MeshIndex]
type BucketPosition = tuple[int, int]


def grid_to_pixels(i: int) -> int:
    return i * TILE_SIZE + (TILE_SIZE // 2)
