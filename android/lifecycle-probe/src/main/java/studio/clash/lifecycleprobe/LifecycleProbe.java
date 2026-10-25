package studio.clash.lifecycleprobe;
import android.app.*;
import android.content.*;
import android.os.Bundle;
import android.webkit.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Opt-in instrumentation APK. It is never included in the application artifact. */
public class LifecycleProbe extends Instrumentation {
    private final String target = "studio.clash.android.MainActivity";
    @Override public void onCreate(Bundle args) { super.onCreate(args); start(); }
    private WebView view(Activity activity) throws Exception { var field=activity.getClass().getDeclaredField("webView");field.setAccessible(true);return (WebView)field.get(activity); }
    private String js(Activity activity,String expression) throws Exception {
        AtomicReference<String> result=new AtomicReference<>();CountDownLatch done=new CountDownLatch(1);
        runOnMainSync(()->{try{view(activity).evaluateJavascript(expression,value->{result.set(value);done.countDown();});}catch(Exception error){done.countDown();}});
        if(!done.await(10,TimeUnit.SECONDS))throw new AssertionError("javascript timeout");return result.get();
    }
    private void ready(Activity activity) throws Exception {for(int n=0;n<50;n++){if("true".equals(js(activity,"!!document.querySelector('.desk')")))return;Thread.sleep(200);}throw new AssertionError("page timeout");}
    private void page(Activity activity) throws Exception {js(activity,"document.querySelectorAll('.mobile-navigation>button')[3].click();true");Thread.sleep(200);}
    private Activity rebuild(Activity activity,String mode) throws Exception {
        ActivityMonitor monitor=addMonitor(target,null,false);
        AtomicBoolean accepted=new AtomicBoolean(true);
        WebView old=view(activity);
        runOnMainSync(()->{
            if(mode.equals("activity")) activity.recreate();
            else if(mode.equals("reclaim")){WebViewRenderProcess renderer=old.getWebViewRenderProcess();accepted.set(renderer!=null&&renderer.terminate());}
            else old.loadUrl("chrome://crash");
        });
        if(!accepted.get()) {removeMonitor(monitor);throw new AssertionError("renderer termination unavailable");}
        Activity next=waitForMonitorWithTimeout(monitor,20000);removeMonitor(monitor);
        if(next==null||next==activity)throw new AssertionError("recreation timeout");ready(next);
        if(!mode.equals("activity")&&view(activity)!=null)throw new AssertionError("dead WebView reference retained");
        if(!mode.equals("activity")&&old.getParent()!=null)throw new AssertionError("dead WebView attached");
        return next;
    }
    @Override public void onStart() {
        Bundle result=new Bundle();Activity activity=null;
        try {
            activity=startActivitySync(new Intent(Intent.ACTION_MAIN).setClassName("studio.clash.android.validation",target).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));ready(activity);
            java.io.File fixture=new java.io.File(getTargetContext().getCacheDir(),"qr-review.png");
            try {
                try(java.io.InputStream input=getContext().getAssets().open("qr-review.png");java.io.OutputStream output=new java.io.FileOutputStream(fixture)) { byte[] bytes=new byte[8192];int count;while((count=input.read(bytes))!=-1)output.write(bytes,0,count); }
                Class<?> qr=Class.forName("studio.clash.android.SubscriptionQr",true,activity.getClassLoader());
                java.lang.reflect.Method decode=null;
                for(var method:qr.getDeclaredMethods())if(method.getName().equals("decode")){decode=method;break;}
                if(decode==null)throw new AssertionError("photo decoder missing");decode.setAccessible(true);
                Object decoded=decode.invoke(null,activity,android.net.Uri.fromFile(fixture));
                if(!"https://example.invalid/clash-review-qr".equals(decoded))throw new AssertionError("photo decode mismatch");
                result.putString("photo_bitmap_decode","passed");
            } finally { fixture.delete(); }
            page(activity);activity=rebuild(activity,"activity");
            if(!"\"connections\"".equals(js(activity,"document.querySelector('.desk').dataset.uiPage")))throw new AssertionError("activity page lost");
            result.putString("activity_recreation","passed");
            page(activity);activity=rebuild(activity,"reclaim");
            if(!"\"connections\"".equals(js(activity,"document.querySelector('.desk').dataset.uiPage")))throw new AssertionError("reclaimed renderer page lost");
            result.putString("renderer_reclaim","passed");
            page(activity);activity=rebuild(activity,"crash");
            if(!"\"home\"".equals(js(activity,"document.querySelector('.desk').dataset.uiPage")))throw new AssertionError("crash did not reset page");
            result.putString("renderer_crash","passed");
            activity=rebuild(activity,"reclaim");
            if(!"\"home\"".equals(js(activity,"document.querySelector('.desk').dataset.uiPage")))throw new AssertionError("stale page restored after crash reset");
            result.putString("crash_reset_survives_reclaim","passed");
            finish(Activity.RESULT_OK,result);
        } catch(Throwable error){result.putString("failure",error.getClass().getSimpleName()+": "+error.getMessage());finish(Activity.RESULT_CANCELED,result);}
    }
}
