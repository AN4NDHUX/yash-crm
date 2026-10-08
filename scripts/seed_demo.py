from app.main import Base, SessionLocal, engine, seed_defaults


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_defaults(db)
    print("CONVOSIS CRM demo seed complete")
