frappe.ui.form.on('External Service Provider', {
	refresh: function(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__('Generate API Key'), function() {
				frappe.confirm(
					__('This will replace any existing API key. The old key will stop working immediately. Continue?'),
					function() {
						frappe.call({
							method: 'ibelong_system.referral_api.generate_api_key',
							args: { provider_name: frm.doc.name },
							callback: function(r) {
								if (r.message && r.message.api_key) {
									frappe.msgprint({
										title: __('New API Key Generated'),
										message: __('Copy this key and share it securely with the provider. It will not be shown again in full.')
											+ '<br><br><code style="font-size:13px;word-break:break-all;">'
											+ r.message.api_key + '</code>',
										indicator: 'green'
									});
									frm.reload_doc();
								}
							}
						});
					}
				);
			}, __('Actions'));
		}
	}
});
