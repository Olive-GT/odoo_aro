# migrations/18.0.2.0/pre-migrate.py


def migrate(cr, version):
    """Retira la vista de Ajustes de la version anterior antes de cargar la nueva.

    La version 18.0.1.0 mostraba en Ajustes los campos `isr_account_id` e
    `isr_account_client_id`, que ya no existen: las cuentas viven ahora en cada
    tipo de retencion. La vista nueva tiene otro identificador, asi que la vieja
    seguia en la base durante la actualizacion y Odoo se negaba a cargar el
    modulo ("El campo isr_account_id no existe"). Los parametros de sistema con
    las cuentas no se tocan: los lee el post-migrate.
    """
    if not version:
        return
    cr.execute("""
        DELETE FROM ir_ui_view
         WHERE id IN (SELECT res_id
                        FROM ir_model_data
                       WHERE module = 'l10n_gt_aro_accounting'
                         AND model = 'ir.ui.view'
                         AND name = 'res_config_settings_view_form_inherit_isr')
    """)
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'l10n_gt_aro_accounting'
           AND model = 'ir.ui.view'
           AND name = 'res_config_settings_view_form_inherit_isr'
    """)
