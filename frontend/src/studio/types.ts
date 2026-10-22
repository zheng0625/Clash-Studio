export interface Proxy { name: string; type: string; server?: string; port?: number; [key: string]: any }
export interface Group { name: string; type: string; proxies?: string[]; use?: string[]; url?: string; interval?: number; [key: string]: any }
export interface Config { proxies?: Proxy[]; 'proxy-groups'?: Group[]; rules?: string[]; [key: string]: any }
export interface Edits {
  proxy_renames: Record<string,string>; excluded_proxies: string[];
  group_overrides: Record<string,Partial<Group>>; deleted_groups: string[]; new_groups: Group[];
  removed_rules: string[]; added_rules: string[]; rule_order: string[];
  ai_routing: { group: string; enabled?: boolean } | null;
}
export interface Preview { yaml: string; config: Config; errors: string[]; warnings: string[]; ai_routing?: {rule_count:number; overridden:number; group:string}|null }
export interface AICatalogue {version:string; group_name:string; service_count:number; rule_count:number; services:{name:string;rules:{type:string;domain:string}[]}[]}
export interface Summary {
  id: string; title: string; source_type: 'url'|'file'|'demo'; source_host: string;
  revision: number; enabled: boolean; interval_minutes: number;
  created_at: string; updated_at: string; refreshed_at: string; last_error: string;
  proxy_count: number; group_count: number; rule_count: number;
}
export interface Subscription extends Summary {
  source_url: string; source: Config; source_yaml: string; edits: Edits;
  preview: Preview; subscription_path: string;
}
export interface History { id: number; label: string; created_at: string; size: number }
export interface NetworkStatus {
  enabled:boolean; port:number; selected_host:string; addresses:{address:string;preferred:boolean}[];
  running:boolean; base_url:string; error:string;
}
