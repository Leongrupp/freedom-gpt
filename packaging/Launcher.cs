using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
[assembly: AssemblyTitle("Freedom GPT")]
[assembly: AssemblyVersion("1.6.0.0")]
class Launcher {
 [STAThread] static void Main() {
  try {
   string root=Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
   Directory.CreateDirectory(Path.Combine(root,".tmp"));
   var info=new ProcessStartInfo(Path.Combine(root,"runtime","python","pythonw.exe"),"-s \""+Path.Combine(root,"launch.py")+"\"");
   info.WorkingDirectory=root;info.UseShellExecute=false;info.CreateNoWindow=true;
   info.EnvironmentVariables["TEMP"]=Path.Combine(root,".tmp");info.EnvironmentVariables["TMP"]=Path.Combine(root,".tmp");
   Process.Start(info);
  } catch(Exception error) {MessageBox.Show(error.Message,"Freedom GPT",MessageBoxButtons.OK,MessageBoxIcon.Error);}
 }
}
