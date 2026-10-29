from sqlalchemy.orm import Session


def ensure_outer_transaction(session: Session, *, immediate: bool = False) -> None:
    connection = session.connection()
    if connection.dialect.name == "sqlite":
        driver = connection.connection.driver_connection
        if driver is not None and not driver.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE" if immediate else "BEGIN")
