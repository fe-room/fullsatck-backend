from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.schemas.product import ProductCreate


class ProductService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_product(
        self,
        payload: ProductCreate,
    ) -> Product:

        product = Product(
            name=payload.name,
            price=payload.price,
            stock=payload.stock,
        )
        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product)
        return product
