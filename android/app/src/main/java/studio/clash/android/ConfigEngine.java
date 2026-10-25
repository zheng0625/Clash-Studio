package studio.clash.android;

import org.json.JSONArray;
import org.json.JSONObject;
import org.yaml.snakeyaml.LoaderOptions;
import org.yaml.snakeyaml.Yaml;
import org.yaml.snakeyaml.constructor.SafeConstructor;
import java.util.*;

/** Bounded, safe YAML loading and structural editing; Mihomo validation is separate. */
final class ConfigEngine {
    static List<Object> items(JSONArray array) throws Exception {
        List<Object> result = new ArrayList<>();
        for (int i = 0; i < array.length(); i++) result.add(array.get(i));
        return result;
    }
    static Set<String> keys(JSONObject object) {
        Set<String> result = new LinkedHashSet<>();
        Iterator<String> keys = object.keys();
        while (keys.hasNext()) result.add(keys.next());
        return result;
    }
    static final int MAX_BYTES = 8 * 1024 * 1024;
    static JSONObject copy(JSONObject value) throws Exception { return new JSONObject(value.toString()); }
    static JSONObject edits() throws Exception { return new JSONObject("{\"proxy_renames\":{},\"excluded_proxies\":[],\"group_overrides\":{},\"deleted_groups\":[],\"new_groups\":[],\"removed_rules\":[],\"added_rules\":[],\"rule_order\":[],\"ai_routing\":null}"); }
    private static Yaml yaml() {
        LoaderOptions options = new LoaderOptions();
        options.setAllowDuplicateKeys(false);
        options.setMaxAliasesForCollections(25);
        options.setNestingDepthLimit(40);
        options.setCodePointLimit(MAX_BYTES);
        return new Yaml(new SafeConstructor(options));
    }
    static JSONObject parse(String text) throws Exception {
        if (text.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > MAX_BYTES) throw new IllegalArgumentException("配置文件不能超过 8 MB");
        Object value = yaml().load(text);
        Object plain = plain(value, 0, new int[]{200_000});
        if (!(plain instanceof JSONObject)) throw new IllegalArgumentException("请导入 Clash YAML 配置，顶层必须是对象");
        JSONObject config = (JSONObject) plain;
        for (String field : Arrays.asList("proxies", "proxy-groups", "rules")) {
            if (config.has(field) && !(config.opt(field) instanceof JSONArray)) throw new IllegalArgumentException(field + " 必须是列表");
            if (!config.has(field)) config.put(field, new JSONArray());
        }
        if (config.getJSONArray("proxies").length() > 10000 || config.getJSONArray("proxy-groups").length() > 2000 || config.getJSONArray("rules").length() > 100000) throw new IllegalArgumentException("节点、策略组或规则数量超过安卓端限制");
        for (String field : Arrays.asList("proxies", "proxy-groups")) for (Object item : items(config.getJSONArray(field))) {
            if (!(item instanceof JSONObject) || !(((JSONObject)item).opt("name") instanceof String)) throw new IllegalArgumentException(field + " 成员必须是具有字符串名称的对象");
        }
        strings(config.getJSONArray("rules"));
        if (config.getJSONArray("proxies").length() == 0 && config.getJSONArray("proxy-groups").length() == 0 && !config.has("proxy-providers")) throw new IllegalArgumentException("配置中没有代理节点、策略组或 Provider");
        return config;
    }
    /**
     * Subscription panels send unrecognised clients a notice-only stub: no proxies or providers,
     * and the "download another client" text sits in group names or members. Never publish such a
     * stub as a working profile; malformed YAML is left to the normal import/refresh errors.
     */
    static void rejectClientNotice(String yaml) throws Exception {
        JSONObject config;
        try { config = parse(yaml); } catch (Exception error) { return; }
        if (config.getJSONArray("proxies").length() > 0 || config.has("proxy-providers")) return;
        List<String> messages = new ArrayList<>();
        for (Object item : items(config.getJSONArray("proxy-groups"))) {
            JSONObject group = (JSONObject)item;
            messages.add(group.optString("name", ""));
            JSONArray members = group.optJSONArray("proxies");
            if (members != null) for (Object member : items(members)) messages.add(String.valueOf(member));
        }
        for (String message : messages) {
            String lower = message.toLowerCase(Locale.ROOT);
            if (message.contains("下载") && (lower.contains("clash") || lower.contains("mihomo") || lower.contains("客户端")))
                throw new ProfileStore.Failure(502, "上游返回了下载客户端的提示配置，没有提供实际节点。请检查订阅状态，或从服务商获取 Clash/Mihomo 专用订阅链接；不会将提示配置发布为有效订阅。");
        }
    }
    private static Object plain(Object value, int depth, int[] budget) throws Exception {
        if (depth > 40 || --budget[0] < 0) throw new IllegalArgumentException("配置嵌套过深或 YAML 引用展开过大");
        if (value == null) return JSONObject.NULL;
        if (value instanceof Map) {
            JSONObject result = new JSONObject();
            for (Map.Entry<?,?> entry : ((Map<?,?>)value).entrySet()) {
                if (!(entry.getKey() instanceof String)) throw new IllegalArgumentException("配置字段名称必须是字符串");
                result.put((String)entry.getKey(), plain(entry.getValue(), depth + 1, budget));
            }
            return result;
        }
        if (value instanceof Collection) {
            JSONArray result = new JSONArray();
            for (Object item : (Collection<?>)value) result.put(plain(item, depth + 1, budget));
            return result;
        }
        if (value instanceof String || value instanceof Boolean || value instanceof Number) return value;
        throw new IllegalArgumentException("配置包含不支持的 YAML 数据类型");
    }
    private static Object javaValue(Object value) throws Exception {
        if (value == JSONObject.NULL) return null;
        if (value instanceof JSONObject) {
            Map<String,Object> map = new LinkedHashMap<>();
            JSONObject object = (JSONObject)value;
            for (String key : keys(object)) map.put(key, javaValue(object.get(key)));
            return map;
        }
        if (value instanceof JSONArray) {
            List<Object> list = new ArrayList<>();
            for (Object item : items((JSONArray)value)) list.add(javaValue(item));
            return list;
        }
        return value;
    }
    static String dump(JSONObject config) throws Exception { return yaml().dump(javaValue(config)); }
    static Set<String> strings(JSONArray values) throws Exception {
        Set<String> result = new LinkedHashSet<>();
        for (Object item : items(values)) {
            if (!(item instanceof String)) throw new IllegalArgumentException("列表成员必须是字符串");
            result.add((String)item);
        }
        return result;
    }
    static JSONObject preview(JSONObject source, JSONObject edits) throws Exception {
        JSONObject config = copy(source), renames = edits.getJSONObject("proxy_renames");
        JSONObject ai = edits.optJSONObject("ai_routing");
        if (ai != null && ai.optBoolean("enabled", true)) throw new IllegalArgumentException("安卓端暂未接入 AI 分流预设");
        Map<String,String> names = new HashMap<>();
        JSONArray nodes = new JSONArray(), groups = new JSONArray();
        Set<String> excluded = strings(edits.getJSONArray("excluded_proxies"));
        for (Object item : items(config.getJSONArray("proxies"))) {
            JSONObject node = (JSONObject)item;
            String old = node.getString("name"), name = renames.optString(old, old);
            names.put(old, name);
            if (!excluded.contains(old)) { node.put("name", name); nodes.put(node); }
        }
        JSONObject overrides = edits.getJSONObject("group_overrides");
        Set<String> deleted = strings(edits.getJSONArray("deleted_groups"));
        for (Object item : items(config.getJSONArray("proxy-groups"))) {
            JSONObject group = (JSONObject)item;
            String old = group.getString("name");
            JSONObject patch = overrides.optJSONObject(old);
            if (patch != null) for (String key : keys(patch)) group.put(key, patch.get(key));
            names.put(old, group.getString("name"));
            if (!deleted.contains(old)) groups.put(group);
        }
        for (Object item : items(edits.getJSONArray("new_groups"))) groups.put(copy((JSONObject)item));
        for (Object item : items(groups)) {
            JSONObject group = (JSONObject)item;
            if (group.has("proxies")) {
                JSONArray members = new JSONArray();
                for (String member : strings(group.getJSONArray("proxies"))) if (!excluded.contains(member)) members.put(names.getOrDefault(member, member));
                group.put("proxies", members);
            }
        }
        config.put("proxies", nodes).put("proxy-groups", groups);
        LinkedHashSet<String> rules = new LinkedHashSet<>();
        Set<String> removed = strings(edits.getJSONArray("removed_rules"));
        for (String rule : strings(config.getJSONArray("rules"))) if (!removed.contains(rule)) rules.add(rule);
        rules.addAll(strings(edits.getJSONArray("added_rules")));
        List<String> ordered = new ArrayList<>();
        for (String rule : strings(edits.getJSONArray("rule_order"))) if (rules.remove(rule)) ordered.add(rule);
        int finalIndex = ordered.size();
        for (int i = 0; i < ordered.size(); i++) if (ordered.get(i).matches("^(MATCH|FINAL),.*")) { finalIndex = i; break; }
        ordered.addAll(finalIndex, rules);
        JSONArray outputRules = new JSONArray();
        for (String rule : ordered) {
            String[] parts = rule.split(",", -1);
            int target = parts.length - (rule.endsWith(",no-resolve") ? 2 : 1);
            if (target > 0 && !parts[0].equals("SUB-RULE")) parts[target] = names.getOrDefault(parts[target], parts[target]);
            outputRules.put(String.join(",", parts));
        }
        config.put("rules", outputRules);
        JSONArray errors = validate(config);
        return new JSONObject().put("config", config).put("yaml", dump(config)).put("errors", errors)
            .put("warnings", new JSONArray().put("安卓结构检查已完成；真实运行前仍需 Mihomo 校验"));
    }
    private static JSONArray validate(JSONObject config) throws Exception {
        JSONArray errors = new JSONArray();
        Set<String> available = new HashSet<>(Arrays.asList("DIRECT", "REJECT", "REJECT-DROP", "PASS", "COMPATIBLE"));
        Map<String,JSONObject> groups = new HashMap<>();
        for (String field : Arrays.asList("proxies", "proxy-groups")) for (Object item : items(config.getJSONArray(field))) {
            if (!(item instanceof JSONObject)) { errors.put(field + " 成员必须是对象"); continue; }
            JSONObject object = (JSONObject)item;
            String name = object.optString("name", "").trim();
            if (name.isEmpty() || !available.add(name)) errors.put("名称为空或重复：" + name);
            if (object.optString("type", "").isEmpty()) errors.put("缺少协议或策略类型：" + name);
            if (field.equals("proxy-groups")) groups.put(name, object);
        }
        for (JSONObject group : groups.values()) {
            JSONArray members = group.optJSONArray("proxies");
            if (members != null) for (String member : strings(members)) if (!available.contains(member)) errors.put("策略组引用不存在：" + member);
            if ((members == null || members.length() == 0) && group.optJSONArray("use") == null) errors.put("策略组没有成员：" + group.optString("name"));
        }
        for (String group : groups.keySet()) if (cycle(group, groups, new HashSet<>(), new HashSet<>())) { errors.put("策略组存在循环引用或嵌套过深：" + group); break; }
        for (String rule : strings(config.getJSONArray("rules"))) {
            String[] parts = rule.split(",", -1);
            int index = parts.length - (rule.endsWith(",no-resolve") ? 2 : 1);
            if (index < 1 || parts[0].isEmpty()) errors.put("规则格式无效：" + rule);
            else if (!parts[0].equals("SUB-RULE") && !available.contains(parts[index])) errors.put("规则引用不存在：" + parts[index]);
        }
        return errors;
    }
    private static boolean cycle(String key, Map<String,JSONObject> groups, Set<String> path, Set<String> done) throws Exception {
        if (path.size() > 64 || path.contains(key)) return true;
        if (done.contains(key) || !groups.containsKey(key)) return false;
        path.add(key);
        JSONArray members = groups.get(key).optJSONArray("proxies");
        if (members != null) for (String name : strings(members)) if (cycle(name, groups, path, done)) return true;
        path.remove(key); done.add(key); return false;
    }
}
