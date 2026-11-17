---
estado: MVP
version: 0.1.0
---

# Seguridad y multi-tenancy

## Modelo de amenaza resumido

- **Aislamiento entre empresas:** el fallo más grave sería filtrar datos de un tenant a otro.
- **Herramientas con efectos:** crear eventos, generar facturas o programar alertas pueden causar daño si se invocan sin control.
- **Credenciales externas:** tokens OAuth y claves de API son objetivo de robo.
- **Datos personales:** nóminas, NIF, IBAN y agendas requieren protección reforzada (GDPR).

## Autenticación (MVP) — implementado

Sin OIDC/Keycloak en el MVP (v2). El servidor acepta dos credenciales:

| Credencial | Cabecera | Uso |
|---|---|---|
| JWT | `Authorization: Bearer <jwt>` | Sesión de usuario/empresa |
| API key | `X-API-Key: <key_id>.<secret>` | Cliente máquina a máquina |

- **API key:** formato `<key_id>.<secret>`; se almacena únicamente el hash **Argon2id** (`argon2-cffi`) de la clave completa, nunca en claro. El prefijo `key_id` permite localizar un único registro sin verificar todos los hashes. El registro incluye `user_id`, `company_id`, `role`, `scopes`, `expires_at` e `is_active`.
- **JWT:** firmado por la instalación con **HS256** (`PyJWT`, sin `python-jose`), claims obligatorios `sub`, `company_id`, `role`, `scopes`, `iat`, `exp`, `iss` y `aud`. Vida máxima por defecto: 30 minutos; el secreto debe tener al menos 32 caracteres.
- **Identidad:** `ToolContext` se construye exclusivamente desde el token o la API key. Nunca se acepta `company_id` del cuerpo de la petición.
- **Confirmación:** las tools con efectos leen `X-PRAXIS-Confirm: true`. El ejecutor también rechaza la llamada si falta, antes de invocar el handler.
- **Modo desarrollo:** `PRAXIS_AUTH_REQUIRED=false` (por defecto en local) crea un contexto con scope comodín `*`. En producción debe valer `true`; un scope `*` real se rechaza.
- **MCP OAuth:** `authlib` se reserva al flujo OAuth de Google Calendar (por usuario), no a la identidad de PRAXIS.
- **2FA/TOTP** (`pyotp`): backlog cercano; barato y demandado por gestorías.

Variables: `PRAXIS_AUTH_REQUIRED`, `PRAXIS_JWT_SECRET` (o `PRAXIS_SECRET_KEY`), `PRAXIS_JWT_ALGORITHM=HS256`, `PRAXIS_JWT_ISSUER`, `PRAXIS_JWT_AUDIENCE`, `PRAXIS_JWT_EXPIRES_MINUTES` y `PRAXIS_API_KEYS_FILE`.

Operación:

```bash
# Genera el hash Argon2id de "key-1.<secret>" para PRAXIS_API_KEYS_FILE
uv run python scripts/hash_api_key.py

# Emite un JWT de desarrollo con el secreto y los claims indicados
PRAXIS_JWT_SECRET=... uv run python scripts/issue_token.py \
  --subject user-1 --company-id 11111111-1111-4111-8111-111111111111 \
  --role admin --scope finance.calculate --minutes 30
```

Formato de `PRAXIS_API_KEYS_FILE` (solo hashes, nunca la clave en claro):

```json
{
  "keys": [
    {
      "key_id": "key-1",
      "key_hash": "$argon2id$v=19$m=65536,t=3,p=4$...",
      "user_id": "user-1",
      "company_id": "11111111-1111-4111-8111-111111111111",
      "role": "manager",
      "scopes": ["finance.calculate", "documents.read"],
      "expires_at": "2027-01-01T00:00:00+00:00",
      "is_active": true
    }
  ]
}
```

### Scopes y permisos

- Scopes por dominio y acción: `finance.calculate`, `calendar.read`, `calendar.write`, `documents.write`, etc.
- `Permission` asocia `tool_name` + `role` a `can_read`, `can_write` y `requires_confirmation`.
- Toda tool declara `permissions`; el ejecutor comprueba que el contexto cubre **todos** los scopes y devuelve `permission_denied` si falta alguno.
- El rechazo por credenciales ausentes o inválidas es HTTP `401` (`authentication_required` / `invalid_token`); el rechazo por scope o confirmación usa el sobre de error de la tool.
- La intersección con `TenantProfile` y `ToolActivation` está implementada mediante `ToolAccessPolicy` inyectable; la persistencia en PostgreSQL sigue pendiente.

## Multi-tenancy

### Aislamiento por RLS

- Todas las tablas tenant-scoped llevan `company_id NOT NULL` y RLS activado.
- Cada conexión fija `app.company_id` desde el `ToolContext` antes de ejecutar.
- Sin contexto, las tablas tenant devuelven cero filas (deny by default).
- Las tablas globales no tienen política y son de solo lectura para tenants.

```sql
ALTER TABLE document ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON document
  USING (company_id = current_setting('app.company_id')::uuid);
```

- Se prueba con `testcontainers[postgres]`: un tenant nunca ve filas de otro.

### Aislamiento en caché

- **Caché compartida** (clima, divisas, geocoding): clave sin `company_id`.
- **Caché operacional** (KPIs, documentos, previsor): clave **incluye** `company_id`.
- Un error de clave de caché es una fuga de datos: se revisa en tests.

### Almacenamiento de documentos

- MVP en el VPS, con nombres opacos (UUID) y ruta fuera del webroot.
- Validación del tipo real con `python-magic` (no por extensión).
- Límite de tamaño y antivirus/escaneo en v2.
- v2: S3/MinIO con URLs firmadas y cifrado en reposo.

## Protección de datos

### Cifrado

- **En tránsito:** TLS obligatorio en producción.
- **En reposo (campos sensibles):** envelope encryption con `cryptography` para `nif`, `salary_gross`, `gross`, `net`, IBAN, tokens OAuth.
- **Rotación de claves:** no se usa `sqlalchemy-utils.EncryptedType`; se implementa sobre cifrado con clave por versión.
- **Secretos de aplicación:** `.env` fuera del repositorio; nunca en git.

### Clasificación

| Clase | Ejemplos | Tratamiento |
|---|---|---|
| `public` | Clima, divisas, unidades, fechas | Sin restricción |
| `business` | Facturas, márgenes, KPIs | RLS + cifrado en exportaciones |
| `personal` | Agenda, NIF, email, teléfono | RLS + cifrado de campos + minimización |
| `sensitive` | Nóminas, salarios, datos de salud | Cifrado de campo + acceso restringido |

### GDPR

- **Base legal y consentimiento:** `DataConsent` por finalidad (`analytics`, `marketing`, `service`).
- **Derecho de acceso y portabilidad:** exportación por `company_id`/`user_id`.
- **Derecho al olvido:** al borrar una empresa se eliminan sus filas tenant (todas con `company_id`); `AuditLog` se anonimiza, no se borra.
- **Minimización:** solo se guardan los datos necesarios para la herramienta.
- **Retención:** política explícita por tabla (ver abajo).
- **Auditoría de acceso a datos personales:** no basta el log de ejecuciones; se registra quién accedió a qué dato personal.

### Retención (propuesta a validar)

| Dato | Retención | Acción |
|---|---|---|
| `ToolExecutionLog` | 12 meses | Borrado o agregación |
| `AuditLog` | 24 meses | Append-only, anonimización |
| `Message` (contenido) | 6 meses | Borrado del contenido, metadatos |
| Documentos | Mientras el tenant exista | Borrado con la empresa |
| Caché operacional | TTL corto | Expiración automática |
| `ConversationContext` | 5 min (Redis) | Expiración |

Estos plazos se documentan como configurables y se validan legalmente (ver [`12-legal-notes.md`](12-legal-notes.md)).

## Herramientas con efectos

- `is_read_only: false` obliga a declarar idempotencia y `idempotency_key`.
- `requires_confirmation: true` en `calendar.create_event`, `documents.generate_invoice` y `alerts.contract_renewal`.
- El ejecutor deduplica centralmente por `scoped_key(tool, company_id, idempotency_key)` con `input_hash` de los parámetros (sin la propia clave) y TTL de 30 días. Reutilizar una clave con parámetros distintos devuelve `conflict`; el almacén es en memoria hasta que exista PostgreSQL.
- Las escrituras se validan contra permisos y tenant antes de ejecutar.

## Rate limiting

- `slowapi`/`fastapi-limiter` por usuario, empresa y herramienta.
- Límites alineados con `ToolActivation.limits_override` y con los proveedores externos.
- Protección contra bucles de un agente: presupuesto de llamadas por ventana.

## Auditoría

`ToolExecutionLog` y `AuditLog` registran:

- `request_id`, usuario, empresa, canal.
- Tool, versión, `execution_method`, `cache_hit`, `provider_calls`.
- `success`/`error`, `warnings`, `legal_disclaimer_shown`.
- Para datos personales, acción y recurso accedido.

`asgi-correlation-id` propaga un `request_id` end-to-end en logs (`structlog` en JSON).

## Checklist de seguridad del MVP

- [ ] RLS activo en todas las tablas tenant + tests de aislamiento.
- [x] API keys hasheadas con Argon2id y nunca logueadas.
- [x] JWT con expiración y validación de scopes.
- [ ] Cifrado de campos sensibles + gestión de claves.
- [ ] Validación de tipo real de archivos subidos.
- [x] `requires_confirmation` en tools con efectos (cabecera de confirmación; UI real pendiente).
- [ ] Rate limiting por tenant/tool.
- [ ] Retención y borrado GDPR documentados e implementados.
- [ ] Secretos fuera del repositorio.
- [ ] Dependencias auditadas (`pip-audit` en CI).
