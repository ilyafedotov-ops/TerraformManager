<script lang="ts">
	import Circle from 'lucide-svelte/icons/circle';
	import Grid from 'lucide-svelte/icons/grid';
	import Sparkles from 'lucide-svelte/icons/sparkles';
	import UploadCloud from 'lucide-svelte/icons/upload-cloud';
	import FileBarChart2 from 'lucide-svelte/icons/file-bar-chart-2';
	import Settings2 from 'lucide-svelte/icons/settings-2';
	import BookOpen from 'lucide-svelte/icons/book-open';
	import SlidersHorizontal from 'lucide-svelte/icons/sliders-horizontal';
	import Bot from 'lucide-svelte/icons/bot';
	import FileIcon from 'lucide-svelte/icons/file';
	import Book from 'lucide-svelte/icons/book';
	import Users from 'lucide-svelte/icons/users';
	import CreditCard from 'lucide-svelte/icons/credit-card';
	import ShieldCheck from 'lucide-svelte/icons/shield-check';

	interface Props {
		name?: string;
		size?: number;
		class?: string;
	}

	type IconComponent = typeof Circle;

	const iconMap = {
		grid: Grid,
		sparkles: Sparkles,
		'upload-cloud': UploadCloud,
		'file-bar-chart-2': FileBarChart2,
		'settings-2': Settings2,
		'book-open': BookOpen,
		'sliders-horizontal': SlidersHorizontal,
		bot: Bot,
		file: FileIcon,
		book: Book,
		users: Users,
		'credit-card': CreditCard,
		'shield-check': ShieldCheck
	} satisfies Record<string, IconComponent>;

	const normaliseKey = (value: string | undefined): string => {
		if (!value) return '';
		return value
			.replace(/([a-z0-9])([A-Z])/g, '$1-$2')
			.replace(/[_\s]+/g, '-')
			.toLowerCase();
	};

	const { name, size = 18, class: className = '' }: Props = $props();

	const iconKey = normaliseKey(name);
	const IconComponent = iconMap[iconKey as keyof typeof iconMap] ?? Circle;
</script>

{#if IconComponent}
	<IconComponent size={size} class={className} />
{/if}
