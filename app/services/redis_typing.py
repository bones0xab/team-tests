from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class RedisStrClient(Protocol):
    """
    Protocol qui décrit un client redis.Redis configuré avec decode_responses=True.
    Toutes les méthodes retournent str (jamais bytes).

    Utilisation :
        from app.services.redis_typing import RedisStrClient
        from typing import cast
        import redis

        raw = redis.Redis(host="redis", decode_responses=True)
        client: RedisStrClient = cast(RedisStrClient, raw)

        val: Optional[str] = client.get("ma_cle")   # ✅ Pyright OK
        ttl: int = client.ttl("ma_cle")              # ✅ Pyright OK
    """

    def ping(self) -> bool:
        """Retourne True si le serveur répond."""
        ...

    def get(self, name: str) -> Optional[str]:
        """Retourne la valeur (str) ou None si la clé n'existe pas."""
        ...

    def set(
        self,
        name: str,
        value: Any,
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
        xx: bool = False,
        keepttl: bool = False,
        get: bool = False,
        exat: Optional[int] = None,
        pxat: Optional[int] = None,
    ) -> Optional[str]:
        """
        SET name value [EX|PX|EXAT|PXAT] [NX|XX] [KEEPTTL] [GET]
        Retourne "OK" si posé, None si NX et clé déjà existante.
        """
        ...

    def delete(self, *names: str) -> int:
        """Supprime une ou plusieurs clés. Retourne le nombre de clés supprimées."""
        ...

    def exists(self, *names: str) -> int:
        """Retourne le nombre de clés existantes parmi celles passées."""
        ...

    def ttl(self, name: str) -> int:
        """
        Retourne le TTL en secondes.
        -1 → clé persistante (pas d'expiration)
        -2 → clé inexistante
        """
        ...

    def keys(self, pattern: str = "*") -> List[str]:
        """Retourne la liste des clés correspondant au pattern."""
        ...

    def info(
        self,
        section: Optional[str] = None,
        *args: Any,
    ) -> Dict[str, Any]:
        """Retourne les informations du serveur Redis."""
        ...

    def setex(self, name: str, time: int, value: Any) -> bool:
        """SET name value EX time. Retourne True si succès."""
        ...