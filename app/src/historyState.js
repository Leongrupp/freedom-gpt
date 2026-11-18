export const messageKey=m=>m.history_uid||m.message_uid;
export function mergeHistory(older,newer){const rows=new Map(older.map(m=>[messageKey(m),m]));for(const m of newer)rows.set(messageKey(m),m);return [...rows.values()].sort((a,b)=>a.history_seq-b.history_seq)}
