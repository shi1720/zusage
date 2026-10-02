import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Compass } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../lib/i18n";
import { Button, Modal } from "./ui";

export const replayTour = () => window.dispatchEvent(new Event("zusage:tour"));
const steps = [
  ["/", "Your next step, made clear", "Today brings together your next interview, due practice and your weekly goal."],
  ["/practice", "Your own practice room", "Choose an apprenticeship, language and interviewer. Training gives feedback after each answer. Dress rehearsal saves it for the end."],
  ["/applications", "Keep every opportunity in view", "Add an apprenticeship, move it between stages and rehearse using its job advert. Removed cards can be restored with Undo."],
  ["/outreach", "Find the words, keep your voice", "Apertus drafts application messages and prep packs using your profile and real experiences. Review every draft before sending."],
  ["/nudges", "Follow up with confidence", "Scan for quiet applications and past interviews. Each reminder comes with a draft you can edit."],
  ["/import", "Bring your existing applications", "Import CSV files or exports from your previous tracker. Download your applications and drafts whenever you need them."],
  ["/profile", "Make it yours", "Add real stories, choose your language and manage privacy. Apertus works immediately. A personal Apertus key is optional."],
];
export function Walkthrough() {
  const { user } = useAuth(); const { t } = useI18n();
  const navigate = useNavigate(); const location = useLocation();
  const { data, refetch } = useQuery({queryKey:["workspace"],queryFn:api.workspace.get});
  const [active,setActive] = useState(false); const [index,setIndex] = useState(0);
  const finish = useMutation({mutationFn:()=>api.workspace.preferences({weekly_goal:data?.weekly_goal ?? 3,tour_complete:true}),onSuccess:()=>void refetch()});
  useEffect(()=>{const replay=()=>{setIndex(0);setActive(true);};window.addEventListener("zusage:tour",replay);return()=>window.removeEventListener("zusage:tour",replay);},[]);
  useEffect(()=>{if(data && !data.tour_complete && user?.onboarded && user.role === "student") setActive(true);},[data?.tour_complete,user?.onboarded,user?.role]);
  const list = user?.role === "student" ? steps : [steps[0],steps[1],steps[6]];
  useEffect(()=>{if(active && location.pathname !== list[index][0])navigate(list[index][0]);},[active,index]);
  if(!active)return null;
  const close=()=>{setActive(false);finish.mutate();};
  return <Modal title={t("A quick tour of Zusage")} onClose={close}>
    <div className="mb-5 flex items-center justify-between"><span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-sign text-lake"><Compass size={25}/></span><span className="text-sm text-ink-3">{index+1} / {list.length}</span></div>
    <div className="mb-6 flex gap-1.5">{list.map((_,i)=><span key={i} className={`h-1.5 flex-1 rounded-full ${i<=index?'bg-lake':'bg-raised'}`}/>)}</div>
    <h2 className="font-display text-2xl font-bold">{t(list[index][1])}</h2><p className="mt-3 text-[15px] leading-relaxed text-ink-2">{t(list[index][2])}</p>
    <div className="mt-7 flex items-center justify-between"><Button onClick={close}>{t("Skip tour")}</Button><div className="flex gap-2">{index>0&&<Button onClick={()=>setIndex(index-1)}>{t("Back")}</Button>}<Button variant="primary" onClick={()=>index===list.length-1?close():setIndex(index+1)}>{t(index===list.length-1?"Let's begin":"Next")}{index===list.length-1?<CheckCircle2 size={16}/>:<ArrowRight size={16}/>}</Button></div></div>
  </Modal>;
}
