"""Cria os 3 usuários (você + 2 filhos) com senha já com hash.

Uso (de dentro de backend/):
  python -m app.seed_users
Edite a lista USERS abaixo antes de rodar (nomes/emails/senhas/níveis).
Rodar de novo NÃO duplica: usa ON DUPLICATE para atualizar senha/nível.
"""
from . import auth
from . import db

# Edite aqui:
USERS = [
    # name, email, password, role, level
    ("Pai",    "pai@casa.local",    "troque-1", "parent", "B2"),
    ("Filho1", "filho1@casa.local", "troque-2", "child",  "B1"),
    ("Filho2", "filho2@casa.local", "troque-3", "child",  "A2"),
]


def run():
    for name, email, password, role, level in USERS:
        ph = auth.hash_password(password)
        db.execute(
            """INSERT INTO users (name, email, password_hash, role, level)
               VALUES (%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE
                 name=VALUES(name), password_hash=VALUES(password_hash),
                 role=VALUES(role), level=VALUES(level)""",
            (name, email.lower(), ph, role, level),
        )
        print(f"  ok: {email}  ({role}, {level})")
    print("Usuários prontos.")


if __name__ == "__main__":
    run()
