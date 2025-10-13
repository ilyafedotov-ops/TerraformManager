import { redirect } from '@sveltejs/kit';

const sectionMeta = [
	{
		match: /^\/dashboard/,
		title: 'Control plane overview',
		subtitle: 'Track reviewer activity and severity trends.',
		breadcrumbs: [{ href: '/dashboard', label: 'Dashboard' }]
	},
	{
		match: /^\/generate/,
		title: 'Terraform generator',
		subtitle: 'Render hardened infrastructure blueprints.',
		breadcrumbs: [
			{ href: '/dashboard', label: 'Dashboard' },
			{ href: '/generate', label: 'Generate' }
		]
	},
	{
		match: /^\/review/,
		title: 'Scan uploads',
		subtitle: 'Submit Terraform for static analysis and remediation hints.',
		breadcrumbs: [
			{ href: '/dashboard', label: 'Dashboard' },
			{ href: '/review', label: 'Review' }
		]
	},
	{
		match: /^\/reports/,
		title: 'Historical reports',
		subtitle: 'Reference past reviewer runs and export findings.',
		breadcrumbs: [
			{ href: '/dashboard', label: 'Dashboard' },
			{ href: '/reports', label: 'Reports' }
		]
	},
	{
		match: /^\/configs/,
		title: 'Reviewer configs',
		subtitle: 'Manage tfreview rules and suppression baselines.',
		breadcrumbs: [
			{ href: '/dashboard', label: 'Dashboard' },
			{ href: '/configs', label: 'Configs' }
		]
	},
	{
		match: /^\/knowledge/,
		title: 'Knowledge base',
		subtitle: 'Search RAG snippets and sync documentation sources.',
		breadcrumbs: [
			{ href: '/dashboard', label: 'Dashboard' },
			{ href: '/knowledge', label: 'Knowledge' }
		]
	},
	{
		match: /^\/settings\/sessions/,
		title: 'Session security',
		subtitle: 'Review active device sessions and revoke refresh tokens.',
		breadcrumbs: [
			{ href: '/dashboard', label: 'Dashboard' },
			{ href: '/settings/sessions', label: 'Settings · Sessions' }
		]
	},
	{
		match: /^\/settings\/llm/,
		title: 'Workspace settings',
		subtitle: 'Configure LLM providers, tokens, and beta features.',
		breadcrumbs: [
			{ href: '/dashboard', label: 'Dashboard' },
			{ href: '/settings/llm', label: 'Settings · LLM' }
		]
	},
	{
		match: /^\/settings/,
		title: 'Workspace settings',
		subtitle: 'Configure workspace preferences and security controls.',
		breadcrumbs: [
			{ href: '/dashboard', label: 'Dashboard' },
			{ href: '/settings/llm', label: 'Settings' }
		]
	}
] as const;

const resolveSection = (pathname: string) => {
	for (const entry of sectionMeta) {
		if (entry.match.test(pathname)) {
			return {
				title: entry.title,
				subtitle: entry.subtitle,
				breadcrumbs: entry.breadcrumbs
			};
		}
	}
	return {
		title: 'Terraform Manager',
		subtitle: 'Secure infrastructure at speed.',
		breadcrumbs: [{ href: '/dashboard', label: 'Dashboard' }]
	};
};

export const load = ({ locals, url }) => {
	const token = locals.token;

	if (!token) {
		const redirectTarget =
			url.pathname === '/login' ? '/login' : `/login?redirect=${encodeURIComponent(url.pathname + url.search)}`;
		throw redirect(302, redirectTarget);
	}

	return {
		token,
		user: locals.user,
		section: resolveSection(url.pathname)
	};
};
