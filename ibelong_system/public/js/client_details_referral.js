frappe.ui.form.on('Client Details', {
	refresh(frm) {
		if (frm.is_new()) return;

		// Best-effort: add to the custom button group in the page header.
		// This may be cleared by workflow state rendering, which is why we also
		// embed the action buttons directly inside the referral section below.
		_add_referral_buttons(frm);
		[200, 800, 2000].forEach(ms => setTimeout(() => _add_referral_buttons(frm), ms));

		// Monkey-patch so our buttons survive any call to clear_custom_buttons()
		if (!frm._ibelong_referral_hooked) {
			frm._ibelong_referral_hooked = true;
			const _orig = frm.clear_custom_buttons.bind(frm);
			frm.clear_custom_buttons = function() {
				_orig();
				setTimeout(() => _add_referral_buttons(frm), 0);
			};
		}

		setTimeout(() => load_referral_section(frm), 300);
	}
});

function _add_referral_buttons(frm) {
	if (!frm || frm.is_new()) return;
	frm.add_custom_button(__('New Referral'), function() {
		frappe.new_doc('Client Referral', { client: frm.doc.name });
	}, __('Referrals'));
	frm.add_custom_button(__('View All Referrals'), function() {
		frappe.set_route('List', 'Client Referral', { client: frm.doc.name });
	}, __('Referrals'));
}

const STATUS_COLOUR = {
	'Pending':     'orange',
	'Sent':        'blue',
	'Accepted':    'green',
	'In Progress': 'purple',
	'Completed':   'green',
	'Closed':      'gray',
	'Declined':    'red'
};

function build_referral_html(frm, referrals) {
	const count     = referrals.length;
	const client_id = (frm.doc.name || '').replace(/'/g, "\\'");

	let rows = '';
	if (count === 0) {
		rows = `<tr><td colspan="5" style="text-align:center;color:#888;padding:10px">
					No referrals for this client yet.
				</td></tr>`;
	} else {
		rows = referrals.map(ref => {
			const colour       = STATUS_COLOUR[ref.referral_status] || 'gray';
			const display_date = ref.referral_date
				? frappe.datetime.str_to_user(ref.referral_date)
				: '—';
			const reason = ref.referral_reason
				? frappe.utils.escape_html(ref.referral_reason).substring(0, 55)
				  + (ref.referral_reason.length > 55 ? '…' : '')
				: '—';
			const safe_name = frappe.utils.escape_html(ref.name);

			return `<tr style="cursor:pointer"
						onclick="frappe.set_route('Form','Client Referral','${safe_name}')">
						<td style="font-weight:600">${safe_name}</td>
						<td>${frappe.utils.escape_html(ref.referred_to || '—')}</td>
						<td>
							<span class="indicator-pill ${colour}" style="font-size:11px">
								${frappe.utils.escape_html(ref.referral_status)}
							</span>
						</td>
						<td style="white-space:nowrap">${display_date}</td>
						<td style="color:#555;font-size:12px">${reason}</td>
					</tr>`;
		}).join('');
	}

	return `
		<div class="ibelong-referral-section"
		     style="margin:12px 0 4px 0; border:1px solid #d1d8dd;
		            border-radius:6px; overflow:hidden">
			<div style="background:#f5f7fa; padding:8px 12px;
			            border-bottom:1px solid #d1d8dd;
			            display:flex; justify-content:space-between; align-items:center">
				<div style="display:flex; align-items:center; gap:8px">
					<span style="font-weight:600; font-size:13px; color:#1f272e">Referrals</span>
					<span style="background:#5e64ff; color:#fff; border-radius:10px;
					      padding:2px 9px; font-size:11px; font-weight:600">${count}</span>
				</div>
				<div style="display:flex; gap:6px">
					<button class="btn btn-xs btn-primary"
					        onclick="frappe.new_doc('Client Referral', {client: '${client_id}'})">
						+ New Referral
					</button>
					<button class="btn btn-xs btn-default"
					        onclick="frappe.set_route('List','Client Referral',{client:'${client_id}'})">
						View All
					</button>
				</div>
			</div>
			<div style="overflow-x:auto">
				<table class="table table-bordered"
				       style="margin:0; font-size:12.5px; border:none">
					<thead>
						<tr style="background:#f9fafb; font-size:11px;
						           text-transform:uppercase; color:#6c757d">
							<th>Referral ID</th>
							<th>Referred To</th>
							<th>Status</th>
							<th>Date</th>
							<th>Reason</th>
						</tr>
					</thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
		</div>`;
}

function load_referral_section(frm) {
	$(frm.wrapper).find('.ibelong-referral-section').remove();

	frappe.call({
		method: 'ibelong_system.referral_api.get_client_referrals',
		args: { client: frm.doc.name },
		callback(r) {
			const referrals = r.message || [];
			const $section  = $(build_referral_html(frm, referrals));

			/* -------------------------------------------------------
			   Strategy 1: find the "Integration Support" section-head
			   and append into that section's body.
			------------------------------------------------------- */
			let inserted = false;

			$(frm.wrapper).find('.section-head').each(function() {
				const heading = $(this).text().trim();
				if (heading.toLowerCase().includes('integration support')) {
					const $body = $(this).closest('.form-section').find('.section-body');
					if ($body.length) {
						$body.append($section);
						inserted = true;
					}
					return false;
				}
			});

			if (inserted) return;

			/* -------------------------------------------------------
			   Strategy 2: alternate Frappe section markup
			------------------------------------------------------- */
			$(frm.wrapper).find('label, .form-section-heading, h6').each(function() {
				const text = $(this).text().trim();
				if (text.toLowerCase().includes('integration support')) {
					$(this).closest('.form-section, .frappe-field-group')
					       .find('.section-body, .control-input-wrapper')
					       .first()
					       .append($section);
					inserted = true;
					return false;
				}
			});

			if (inserted) return;

			console.warn('[iBelong Referrals] "Integration Support" section not found.');
			console.log('[iBelong Referrals] Available section headings:',
				$(frm.wrapper).find('.section-head')
				              .map(function() { return $(this).text().trim(); })
				              .get()
			);
		}
	});
}