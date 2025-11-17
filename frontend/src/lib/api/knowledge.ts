import type { KnowledgeItem, ProjectDetail, ProjectSummary } from '$lib/api/client';
import { searchKnowledge } from '$lib/api/client';

type ProjectLike = ProjectDetail | ProjectSummary | null | undefined;

const collectMetadataValues = (value: unknown, collector: Set<string>) => {
	if (!value) return;
	if (typeof value === 'string') {
		const trimmed = value.trim();
		if (trimmed) {
			collector.add(trimmed);
		}
		return;
	}
	if (Array.isArray(value)) {
		for (const entry of value) {
			collectMetadataValues(entry, collector);
		}
		return;
	}
	if (typeof value === 'object') {
		for (const entry of Object.values(value)) {
			collectMetadataValues(entry, collector);
		}
	}
};

export interface ProjectKnowledgeContext {
	project?: ProjectLike;
	generatorSlugs?: string[];
	extraTags?: string[];
}

export const deriveProjectKnowledgeKeywords = ({
	project,
	generatorSlugs = [],
	extraTags = []
}: ProjectKnowledgeContext): string[] => {
	const keywords = new Set<string>();
	if (project?.name) {
		keywords.add(project.name);
	}
	if (project?.slug) {
		keywords.add(project.slug);
	}
	if (project?.description) {
		keywords.add(project.description);
	}
	if (project?.metadata) {
		collectMetadataValues(project.metadata, keywords);
	}
	for (const slug of generatorSlugs) {
		const cleaned = slug?.trim();
		if (cleaned) {
			keywords.add(cleaned);
		}
	}
	for (const tag of extraTags) {
		const cleaned = tag?.trim();
		if (cleaned) {
			keywords.add(cleaned);
		}
	}

	return Array.from(keywords)
		.map((entry) => entry.replace(/\s+/g, ' ').trim())
		.filter((entry) => entry.length > 1)
		.slice(0, 10);
};

export const buildProjectKnowledgeQuery = (context: ProjectKnowledgeContext): string | null => {
	const keywords = deriveProjectKnowledgeKeywords(context);
	if (!keywords.length) {
		return null;
	}
	return keywords.join(' ');
};

export const fetchProjectKnowledge = async (
	fetchFn: typeof fetch,
	context: ProjectKnowledgeContext,
	topK = 3
): Promise<{ items: KnowledgeItem[]; query: string | null }> => {
	const query = buildProjectKnowledgeQuery(context);
	if (!query) {
		return { items: [], query: null };
	}
	const items = await searchKnowledge(fetchFn, query, topK);
	return { items, query };
};
