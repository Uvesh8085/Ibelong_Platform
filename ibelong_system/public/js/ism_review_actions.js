frappe.ui.form.on('Client Details', {
	refresh(frm) {
		if (frm.is_new()) return;

		_add_ism_buttons(frm);
		[200, 800, 2000].forEach(ms => setTimeout(() => _add_ism_buttons(frm), ms));

		if (!frm._ibelong_ism_hooked) {
			frm._ibelong_ism_hooked = true;
			const _orig = frm.clear_custom_buttons.bind(frm);
			frm.clear_custom_buttons = function() {
				_orig();
				setTimeout(() => _add_ism_buttons(frm), 0);
			};
		}
	}
});

function _add_ism_buttons(frm) {
	if (!frm || frm.is_new()) return;

	frm.add_custom_button(__('Submit ISM for Client Review'), function() {
		_pick_booking_and_call(
			frm,
			['ISM Scheduled'],
			'Submit ISM for Client Review',
			'ibelong_system.ism_review.submit_for_client_review',
			'The client has been emailed (and texted, if a mobile number is on file) a confirmation code.'
		);
	}, __('ISM'));

	frm.add_custom_button(__('Close ISM Case'), function() {
		_pick_booking_and_call(
			frm,
			['Case Open', 'Case Referred'],
			'Close ISM Case',
			'ibelong_system.ism_review.close_ism_case',
			'The case has been closed.'
		);
	}, __('ISM'));
}

function _booking_label(row) {
	const date = row.slot_date || 'no date';
	const time = row.slot_time || '';
	const officer = row.officer_name ? ` - ${row.officer_name}` : '';
	return `${date} ${time}${officer} [${row.booking_status || 'no status'}]`;
}

function _pick_booking_and_call(frm, eligible_statuses, title, method, success_message) {
	const rows = (frm.doc.ism_bookings || []).filter(r => eligible_statuses.includes(r.booking_status));

	if (!rows.length) {
		frappe.msgprint(__('No ISM bookings are in a status eligible for this action ({0}).', [eligible_statuses.join(' / ')]));
		return;
	}

	const options = rows.map(r => ({ label: _booking_label(r), value: r.name }));

	const d = new frappe.ui.Dialog({
		title: __(title),
		fields: [
			{
				fieldname: 'booking',
				fieldtype: 'Autocomplete',
				label: __('ISM Booking'),
				options: options.map(o => o.label),  // Show readable labels in the list
				reqd: 1,
				onchange: function(e) {
					// When the user picks a label, find the corresponding booking id
					const selectedLabel = this.get_value();
					const match = options.find(o => o.label === selectedLabel);
					if (match) {
						this._booking_id = match.value;
					}
				}
			}
		],
		primary_action_label: __(title),
		primary_action(values) {
			// Use the stored booking ID (actual child-row name), not the label
			const booking_id = d.fields_dict.booking._booking_id || values.booking;
			frappe.call({
				method: method,
				args: { booking: booking_id },
				freeze: true,
				callback: function(r) {
					if (r.exc) return;
					d.hide();
					frappe.msgprint(__(success_message));
					frm.reload_doc();
				}
			});
		}
	});

	d.show();
}
