#!/bin/bash
# Extrae de Odoo General (17) todo lo de una empresa en un rango de fechas.
# SOLO LECTURA: no modifica nada en el origen.
#   sudo bash extraer.sh <company_id> <desde> <hasta> [carpeta]
# Deja un archivo .jsonl por tabla (una fila JSON por línea) y los adjuntos.
set -euo pipefail
CID=${1:?company_id}; D1=${2:?desde AAAA-MM-DD}; D2=${3:?hasta AAAA-MM-DD}; OUT=${4:-/tmp/ozu_export}
DB=${DB:-general}; FILESTORE=${FILESTORE:-/mnt/odoo-config/odoo-data/filestore/$DB}
rm -rf "$OUT"; mkdir -p "$OUT/archivos"; chmod 777 "$OUT"
q() { # q <nombre> <consulta>: una fila JSON por línea
  sudo -u postgres psql -At -d "$DB" -v ON_ERROR_STOP=1 -c "select row_to_json(x) from ($2) x" > "$OUT/$1.jsonl"
  printf '%-22s %s\n' "$1" "$(wc -l < "$OUT/$1.jsonl")"
}
M="(select id from account_move where company_id=$CID and date between '$D1' and '$D2')"
# órdenes: las del rango y las que factura algún asiento del rango
PO="(select id from purchase_order where company_id=$CID and date_order >= '$D1' and date_order < ('$D2'::date + 1)
     union select pl.order_id from account_move_line l join purchase_order_line pl on pl.id=l.purchase_line_id where l.move_id in $M)"
SO="(select id from sale_order where company_id=$CID and date_order >= '$D1' and date_order < ('$D2'::date + 1)
     union select sl.order_id from sale_order_line_invoice_rel r join sale_order_line sl on sl.id=r.order_line_id join account_move_line l on l.id=r.invoice_line_id where l.move_id in $M)"
MSG="(select id from mail_message where message_type='comment' and ((model='purchase.order' and res_id in $PO) or (model='sale.order' and res_id in $SO)))"
ATT="(select id from ir_attachment where type='binary' and res_field is null and ((res_model='purchase.order' and res_id in $PO) or (res_model='sale.order' and res_id in $SO) or (res_model='account.move' and res_id in $M))
      union select attachment_id from message_attachment_rel where message_id in $MSG)"
# contactos: todos los que la empresa ha usado alguna vez, más autores de mensajes y usuarios
P="(with base as (
      select partner_id id from account_move where company_id=$CID union select partner_id from account_move_line where company_id=$CID
      union select partner_id from purchase_order where company_id=$CID union select partner_id from sale_order where company_id=$CID
      union select author_id from mail_message where id in $MSG
      union select partner_id from res_users where id in (select user_id from purchase_order where company_id=$CID union select user_id from sale_order where company_id=$CID))
    select id from base where id is not null
    union select rp.parent_id from res_partner rp join base b on b.id=rp.id where rp.parent_id is not null
    union select rp.commercial_partner_id from res_partner rp join base b on b.id=rp.id where rp.commercial_partner_id is not null)"
PROD="(select product_id from account_move_line where company_id=$CID and product_id is not null
       union select l.product_id from purchase_order_line l join purchase_order o on o.id=l.order_id where o.company_id=$CID and l.product_id is not null
       union select l.product_id from sale_order_line l join sale_order o on o.id=l.order_id where o.company_id=$CID and l.product_id is not null)"

echo "== maestros"
q company "select c.id, c.name, c.currency_id, p.vat, p.street, p.street2, p.city, p.zip, p.phone, p.email, p.website from res_company c join res_partner p on p.id=c.partner_id where c.id=$CID"
q currencies "select id, name from res_currency"
q currency_rates "select name, rate, currency_id from res_currency_rate where company_id=$CID"
q uoms "select id, name from uom_uom"
q users "select u.id, u.login, u.partner_id, p.name, p.email from res_users u join res_partner p on p.id=u.partner_id"
q accounts "select id, code, name, account_type, reconcile, deprecated, currency_id, non_trade, note from account_account where company_id=$CID order by code"
q tax_groups "select id, name, sequence from account_tax_group where company_id=$CID or id in (select tax_group_id from account_tax where company_id=$CID)"
q taxes "select id, name, description, invoice_label, amount_type, amount, type_tax_use, price_include, include_base_amount, tax_exigibility, tax_group_id, active, sequence, python_compute from account_tax where company_id=$CID order by sequence, id"
q tax_rep_lines "select r.id, r.tax_id, r.document_type, r.repartition_type, r.factor_percent, r.account_id, r.sequence, r.use_in_tax_closing from account_tax_repartition_line r where r.tax_id in (select id from account_tax where company_id=$CID) order by r.tax_id, r.document_type, r.sequence, r.id"
q journals "select id, name, code, type, default_account_id, currency_id, active, sequence, suspense_account_id, profit_account_id, loss_account_id from account_journal where company_id=$CID order by sequence, id"
q analytic_accounts "select a.id, a.name, a.code, a.active, a.plan_id, pl.name as plan_name from account_analytic_account a join account_analytic_plan pl on pl.id=a.plan_id where a.company_id=$CID or a.id in (select (jsonb_object_keys(analytic_distribution))::int from account_move_line where company_id=$CID and analytic_distribution is not null and analytic_distribution::text !~ ',')"
q partners "select id, name, vat, is_company, parent_id, commercial_partner_id, type, street, street2, city, zip, phone, mobile, email, website, ref, comment, active, supplier_rank, customer_rank, cui, pequenio_contribuyente from res_partner where id in $P order by parent_id nulls first, id"
q products "select pp.id, pp.product_tmpl_id, pp.default_code, pp.active, t.name, t.detailed_type, t.purchase_method, t.invoice_policy, t.uom_id, t.uom_po_id, t.list_price, t.sale_ok, t.purchase_ok, t.description_purchase, t.description_sale from product_product pp join product_template t on t.id=pp.product_tmpl_id where pp.id in $PROD"
q properties "select pr.name, pr.res_id, pr.value_reference, f.model from ir_property pr join ir_model_fields f on f.id=pr.fields_id where pr.company_id=$CID"

echo "== órdenes"
q purchase_orders "select id, name, partner_id, partner_ref, date_order, date_approve, date_planned, currency_id, state, notes, origin, user_id, amount_untaxed, amount_tax, amount_total, invoice_status, create_date from purchase_order where id in $PO order by id"
q purchase_lines "select l.id, l.order_id, l.sequence, l.display_type, l.name, l.product_id, l.product_qty, l.product_uom, l.price_unit, l.discount, l.date_planned, l.qty_received, l.qty_invoiced, l.price_subtotal, l.price_total, l.analytic_distribution, (select array_agg(account_tax_id) from account_tax_purchase_order_line_rel r where r.purchase_order_line_id=l.id) as tax_ids from purchase_order_line l where l.order_id in $PO order by l.order_id, l.sequence, l.id"
q sale_orders "select id, name, partner_id, partner_invoice_id, partner_shipping_id, client_order_ref, date_order, validity_date, currency_id, state, locked, note, origin, user_id, amount_untaxed, amount_tax, amount_total, invoice_status, create_date from sale_order where id in $SO order by id"
q sale_lines "select l.id, l.order_id, l.sequence, l.display_type, l.name, l.product_id, l.product_uom_qty, l.product_uom, l.price_unit, l.discount, l.qty_delivered, l.qty_invoiced, l.price_subtotal, l.price_total, l.analytic_distribution, (select array_agg(account_tax_id) from account_tax_sale_order_line_rel r where r.sale_order_line_id=l.id) as tax_ids from sale_order_line l where l.order_id in $SO order by l.order_id, l.sequence, l.id"

echo "== contabilidad"
q moves "select id, name, ref, date, journal_id, currency_id, state, partner_id, move_type, invoice_date, invoice_date_due, invoice_origin, payment_reference, narration, tipo_gasto, payment_state, amount_untaxed, amount_tax, amount_total, amount_residual, amount_total_signed, reversed_entry_id, payment_id, statement_line_id from account_move where id in $M order by date, id"
q move_lines "select l.id, l.move_id, l.sequence, l.display_type, l.name, l.account_id, l.partner_id, l.currency_id, l.balance, l.debit, l.credit, l.amount_currency, l.amount_residual, l.amount_residual_currency, l.reconciled, l.full_reconcile_id, l.quantity, l.price_unit, l.discount, l.price_subtotal, l.price_total, l.product_id, l.product_uom_id, l.tax_line_id, l.tax_repartition_line_id, l.tax_base_amount, l.date_maturity, l.purchase_line_id, l.analytic_distribution, (select array_agg(account_tax_id) from account_move_line_account_tax_rel r where r.account_move_line_id=l.id) as tax_ids, (select array_agg(order_line_id) from sale_order_line_invoice_rel r where r.invoice_line_id=l.id) as sale_line_ids from account_move_line l where l.move_id in $M order by l.move_id, l.id"
q partials "select p.id, p.debit_move_id, p.credit_move_id, p.amount, p.debit_amount_currency, p.credit_amount_currency, p.full_reconcile_id, p.exchange_move_id from account_partial_reconcile p join account_move_line d on d.id=p.debit_move_id join account_move_line c on c.id=p.credit_move_id where d.move_id in $M and c.move_id in $M order by p.id"

echo "== mensajes y archivos"
q messages "select m.id, m.model, m.res_id, m.date, m.author_id, m.body, m.subject, (select internal from mail_message_subtype s where s.id=m.subtype_id) as interno, (select array_agg(attachment_id) from message_attachment_rel r where r.message_id=m.id) as attachment_ids from mail_message m where m.id in $MSG order by m.id"
q attachments "select id, name, res_model, res_id, store_fname, mimetype, file_size, checksum, description, create_date from ir_attachment where id in $ATT order by id"
sudo -u postgres psql -At -d "$DB" -c "select distinct store_fname from ir_attachment where id in $ATT and store_fname is not null" > "$OUT/_archivos.txt"
( cd "$FILESTORE" && tar cf "$OUT/archivos.tar" -T "$OUT/_archivos.txt" 2>"$OUT/_archivos_faltantes.txt" ) || true
printf '%-22s %s (%s)\n' archivos "$(wc -l < "$OUT/_archivos.txt")" "$(du -sh "$OUT/archivos.tar" | cut -f1)"

echo "== cifras de control"
q control_cuentas "select a.code, round(sum(l.debit),2) debe, round(sum(l.credit),2) haber, count(*) lineas from account_move_line l join account_account a on a.id=l.account_id where l.move_id in $M and l.parent_state='posted' group by 1 order by 1"
q control_contactos "select coalesce(l.partner_id,0) partner_id, a.account_type, round(sum(l.balance),2) saldo, round(sum(l.amount_residual),2) pendiente from account_move_line l join account_account a on a.id=l.account_id where l.move_id in $M and l.parent_state='posted' and a.account_type in ('asset_receivable','liability_payable') group by 1,2 order by 1,2"
q control_analitica "select count(*) lineas, round(sum(amount),2) total from account_analytic_line where move_line_id in (select id from account_move_line where move_id in $M)"
rm -f "$OUT/_archivos.txt"; rmdir "$OUT/archivos" 2>/dev/null || true
tar czf "$OUT.tgz" -C "$(dirname "$OUT")" "$(basename "$OUT")"
ls -la "$OUT.tgz"
