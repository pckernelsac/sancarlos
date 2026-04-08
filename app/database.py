"""
Módulo de base de datos — reemplaza Flask-SQLAlchemy.
Provee un objeto `db` compatible con los patrones existentes de los servicios:
  db.session.add(...), db.session.commit(), Model.query.filter_by(...)
"""
from sqlalchemy import create_engine, func, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import (
    DeclarativeBase, scoped_session, sessionmaker, relationship,
)
from sqlalchemy import (
    Column, Integer, String, Boolean, Text, Date, Enum,
    ForeignKey, UniqueConstraint,
)


class Base(DeclarativeBase):
    pass


class _Database:
    """Capa de compatibilidad que imita la API de Flask-SQLAlchemy."""

    def __init__(self):
        self.engine = None
        self._scoped_session = None

    # --- Aliases de SQLAlchemy (para que los modelos usen db.Column, etc.) ---
    Model = Base
    Column = Column
    Integer = Integer
    String = String
    Boolean = Boolean
    Text = Text
    Date = Date
    Enum = Enum
    ForeignKey = ForeignKey
    UniqueConstraint = UniqueConstraint
    relationship = staticmethod(relationship)
    func = func

    def init(self, database_url: str):
        connect_args = {}
        pool_kw = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            connect_args["timeout"] = 30
            # Una sola conexión compartida: sin esto, cada checkout de pool es un :memory: distinto
            if ":memory:" in database_url:
                pool_kw["poolclass"] = StaticPool
        elif database_url.startswith("postgresql"):
            pool_kw["pool_pre_ping"] = True
            pool_kw["pool_size"] = 5
            pool_kw["max_overflow"] = 10
            pool_kw["pool_recycle"] = 300
        self.engine = create_engine(
            database_url, connect_args=connect_args, **pool_kw
        )
        if database_url.startswith("sqlite") and ":memory:" not in database_url:

            @event.listens_for(self.engine, "connect")
            def _sqlite_pragma(dbapi_conn, _connection_record):
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()
        elif database_url.startswith("sqlite"):

            @event.listens_for(self.engine, "connect")
            def _sqlite_fk_only(dbapi_conn, _connection_record):
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()
        factory = sessionmaker(bind=self.engine, autoflush=True)
        self._scoped_session = scoped_session(factory)
        Base.query = self._scoped_session.query_property()

    @property
    def session(self):
        return self._scoped_session()

    def create_all(self):
        Base.metadata.create_all(self.engine)

    def drop_all(self):
        Base.metadata.drop_all(self.engine)

    def remove_session(self):
        if self._scoped_session:
            self._scoped_session.remove()


db = _Database()
