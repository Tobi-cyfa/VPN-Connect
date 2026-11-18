package com.vpnconnect.app;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * The list shown on the Events tab. Newest entries are returned first.
 *
 * @author zero.cyfa
 */
final class EventLog {
    private static final String PREFS = "vc_events";
    private static final String KEY = "list";
    private static final int MAX = 200;

    static final class Event {
        final long time;
        final String text;
        final boolean ok;

        Event(long time, String text, boolean ok) {
            this.time = time;
            this.text = text;
            this.ok = ok;
        }
    }

    private static EventLog instance;

    private final SharedPreferences prefs;
    private final List<Event> items = new ArrayList<>(); // oldest first

    static synchronized EventLog get(Context context) {
        if (instance == null) {
            instance = new EventLog(context.getApplicationContext());
        }
        return instance;
    }

    private EventLog(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        load();
    }

    synchronized void add(String text, boolean ok) {
        items.add(new Event(System.currentTimeMillis(), text, ok));
        while (items.size() > MAX) {
            items.remove(0);
        }
        save();
    }

    synchronized List<Event> newestFirst() {
        List<Event> copy = new ArrayList<>(items);
        Collections.reverse(copy);
        return copy;
    }

    synchronized void clear() {
        items.clear();
        save();
    }

    private void save() {
        JSONArray arr = new JSONArray();
        try {
            for (Event e : items) {
                JSONObject o = new JSONObject();
                o.put("t", e.time);
                o.put("m", e.text);
                o.put("ok", e.ok);
                arr.put(o);
            }
        } catch (JSONException ex) {
            return;
        }
        prefs.edit().putString(KEY, arr.toString()).apply();
    }

    private void load() {
        items.clear();
        try {
            JSONArray arr = new JSONArray(prefs.getString(KEY, "[]"));
            for (int i = 0; i < arr.length(); i++) {
                JSONObject o = arr.getJSONObject(i);
                items.add(new Event(o.optLong("t"), o.optString("m"), o.optBoolean("ok", true)));
            }
        } catch (JSONException ex) {
            items.clear();
        }
    }
}
