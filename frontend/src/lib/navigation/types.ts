export interface NavigationItem {
	id?: string;
	title: string;
	href?: string;
	icon?: string;
	label?: string;
	items?: NavigationItem[];
	lazyImport?: () => Promise<NavigationItem[]>;
}

export interface NavigationSection {
	title: string;
	items: NavigationItem[];
}
