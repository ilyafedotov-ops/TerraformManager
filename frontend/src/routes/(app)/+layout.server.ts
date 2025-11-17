import { redirect } from '@sveltejs/kit';

type Breadcrumb = { href: string; label: string };

type SectionDefinition = {
	match: RegExp;
	title: string;
	subtitle: string;
	breadcrumbs?: Breadcrumb[] | ((pathname: string) => Breadcrumb[]);
};

const sectionMeta: SectionDefinition[] = [
	{
		match: /^\/projects$/,
		title: 'Project workspace',
		subtitle: 'Select a project to continue.',
		breadcrumbs: [{ href: '/projects', label: 'Projects' }]
	},
	{
		match: /^\/projects\/[^/]+\/dashboard/,
		title: 'Control plane overview',
		subtitle: 'Track reviewer activity and severity trends.',
		breadcrumbs: (pathname) => [
			{ href: '/projects', label: 'Projects' },
			{ href: pathname, label: 'Dashboard' }
		]
	},
	{
		match: /^\/projects\/[^/]+\/generate/,
		title: 'Terraform generator',
		subtitle: 'Render hardened infrastructure blueprints.',
		breadcrumbs: (pathname) => [
			{ href: '/projects', label: 'Projects' },
			{ href: pathname, label: 'Generate' }
		]
	},
	{
		match: /^\/projects\/[^/]+\/review/,
		title: 'Scan uploads',
		subtitle: 'Submit Terraform for static analysis and remediation hints.',
		breadcrumbs: (pathname) => [
			{ href: '/projects', label: 'Projects' },
			{ href: pathname, label: 'Review' }
		]
	},
	{
		match: /^\/projects\/[^/]+\/reports/,
		title: 'Historical reports',
		subtitle: 'Reference past reviewer runs and export findings.',
		breadcrumbs: (pathname) => [
			{ href: '/projects', label: 'Projects' },
			{ href: pathname, label: 'Reports' }
		]
	},
	{
		match: /^\/knowledge/,
		title: 'Knowledge base',
		subtitle: 'Search RAG snippets and sync documentation sources.',
		breadcrumbs: [
			{ href: '/projects', label: 'Projects' },
			{ href: '/knowledge', label: 'Knowledge' }
		]
	},
	{
		match: /^\/settings\/sessions/,
		title: 'Session security',
		subtitle: 'Review active device sessions and revoke refresh tokens.',
		breadcrumbs: [
			{ href: '/projects', label: 'Projects' },
			{ href: '/settings/sessions', label: 'Settings · Sessions' }
		]
	},
	{
		match: /^\/settings\/llm/,
		title: 'Workspace settings',
		subtitle: 'Configure LLM providers, tokens, and beta features.',
		breadcrumbs: [
			{ href: '/projects', label: 'Projects' },
			{ href: '/settings/llm', label: 'Settings · LLM' }
		]
	},
	{
		match: /^\/settings/,
		title: 'Workspace settings',
		subtitle: 'Configure workspace preferences and security controls.',
		breadcrumbs: [
			{ href: '/projects', label: 'Projects' },
			{ href: '/settings/llm', label: 'Settings' }
		]
	}
];

const resolveSection = (pathname: string) => {
	for (const entry of sectionMeta) {
		if (entry.match.test(pathname)) {
			const crumbs = typeof entry.breadcrumbs === 'function'
				? entry.breadcrumbs(pathname)
				: entry.breadcrumbs;
			return {
				title: entry.title,
				subtitle: entry.subtitle,
				breadcrumbs: crumbs ?? [{ href: '/projects', label: 'Projects' }]
			};
		}
	}
	return {
		title: 'Terraform Manager',
		subtitle: 'Secure infrastructure at speed.',
		breadcrumbs: [{ href: '/projects', label: 'Projects' }]
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
