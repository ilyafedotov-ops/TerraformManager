export interface NavigationItem {
	id?: string;
	title: string;
	href?: string;
	icon?: string;
	label?: string;
	items?: NavigationItem[];
	lazyImport?: () => Promise<NavigationItem[]>;
	projectScoped?: boolean;
	projectPath?: string;
}

export interface NavigationSection {
	title: string;
	items: NavigationItem[];
}
