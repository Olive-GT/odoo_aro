# Migración de OZU: Odoo General (17) → Odoo Inmobiliario (18)

Tres piezas, en este orden:

1. `extraer.sh` — corre en el servidor de **General**. Solo lee. Saca a archivos
   todo lo de una empresa en un rango de fechas (maestros, órdenes, asientos,
   conciliaciones, comentarios, adjuntos) y las cifras de control.
   `sudo bash extraer.sh 588 2026-10-01 2026-10-31 /tmp/ozu_export`
2. `cargar.py` — corre dentro de `odoo shell` en el **destino**. Crea la empresa
   y carga lo extraído. Sin `OZU_CONFIRMAR=1` es un ensayo en seco: no guarda.
3. `verificar.py` — corre dentro de `odoo shell` en el destino. No escribe.
   Compara lo cargado contra lo extraído, comprobación por comprobación.

Cada registro creado queda anotado en `ir.model.data` con el módulo `__ozu__`
y el id que tenía en General. Por eso la carga se puede repetir, hacer por
tandas y deshacer.

**Nunca se prueba contra producción.** Se ensaya en una copia de la base de
destino sin salida a internet.
