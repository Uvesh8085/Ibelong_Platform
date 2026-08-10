frappe.ui.form.on('Client Referral', {
	refresh: function(frm) {
		frm.add_custom_button(__('Add Note'), function() {
			let d = new frappe.ui.Dialog({
				title: __('Add Note'),
				fields: [
					{
						label: __('Note'),
						fieldname: 'note',
						fieldtype: 'Small Text',
						reqd: 1
					}
				],
				primary_action_label: __('Add Note'),
				primary_action(values) {
					let row = frm.add_child('notes');
					row.note = values.note;
					row.added_by = frappe.session.user;
					row.added_on = frappe.datetime.now_datetime();
					row.source = 'Internal';
					frm.refresh_field('notes');
					frm.save();
					d.hide();
				}
			});
			d.show();
		});

		// Colour-code status badge in the form header
		if (frm.doc.referral_status) {
			let colour_map = {
				'Pending': 'orange',
				'Sent': 'blue',
				'Accepted': 'green',
				'In Progress': 'purple',
				'Completed': 'green',
				'Closed': 'grey',
				'Declined': 'red'
			};
			let colour = colour_map[frm.doc.referral_status] || 'grey';
			frm.set_indicator_formatter('referral_status', function() { return colour; });
		}
	},

	referral_status: function(frm) {
		if (['Closed', 'Declined'].includes(frm.doc.referral_status)) {
			frm.set_df_property('reason_for_closure', 'reqd', 1);
		} else {
			frm.set_df_property('reason_for_closure', 'reqd', 0);
		}
	}
});
