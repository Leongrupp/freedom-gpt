using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
[assembly: AssemblyTitle("Freedom GPT Setup")]
[assembly: AssemblyVersion("1.2.0.0")]
class SliceStream:Stream {
 Stream input;long start,length,position;
 public SliceStream(Stream source,long offset,long size){input=source;start=offset;length=size;Position=0;}
 public override bool CanRead{get{return true;}} public override bool CanSeek{get{return true;}} public override bool CanWrite{get{return false;}}
 public override long Length{get{return length;}} public override long Position{get{return position;}set{if(value<0||value>length)throw new IOException("Invalid payload position");position=value;input.Position=start+value;}}
 public override int Read(byte[] buffer,int offset,int count){int got=input.Read(buffer,offset,(int)Math.Min(count,length-position));position+=got;return got;}
 public override long Seek(long offset,SeekOrigin origin){Position=(origin==SeekOrigin.Begin?0:origin==SeekOrigin.Current?position:length)+offset;return position;}
 public override void Flush(){} public override void SetLength(long value){throw new NotSupportedException();} public override void Write(byte[] b,int o,int c){throw new NotSupportedException();}
}
class Setup:Form {
 static bool UseEnglish=!System.Globalization.CultureInfo.CurrentUICulture.TwoLetterISOLanguageName.Equals("ru");
 static string L(string ru,string en){return UseEnglish?en:ru;}
 ComboBox language;
 Setup(){Build();}

 TextBox folder;Label status;ProgressBar progress;Button install,browse;CheckBox open,shortcut;
 Color bg=Color.FromArgb(24,24,28),panel=Color.FromArgb(34,34,40),accent=Color.FromArgb(185,166,236);
 static string Self{get{return Assembly.GetExecutingAssembly().Location;}}
 [STAThread] static int Main(string[] args){
  foreach(string arg in args){if(arg=="/lang=en")UseEnglish=true;if(arg=="/lang=ru")UseEnglish=false;}
  string extract=null;foreach(string value in args)if(value.StartsWith("/extract=",StringComparison.OrdinalIgnoreCase))extract=value.Substring(9);
  if(extract!=null){try{Extract(extract,(percent,name)=>{});return 0;}catch(Exception error){File.WriteAllText(Self+".error.txt",error.ToString());return 1;}}
  Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new Setup());return 0;
 }
 Label TextLabel(string text,int x,int y,int width,int height,float size,Color color){var label=new Label{Text=text,Location=new Point(x,y),Size=new Size(width,height),Font=new Font("Segoe UI",size),ForeColor=color,BackColor=Color.Transparent};Controls.Add(label);return label;}
 void Build(){
  Controls.Clear();
  Text=L("Установка Freedom GPT","Installing Freedom GPT");ClientSize=new Size(760,530);BackColor=bg;ForeColor=Color.White;Font=new Font("Segoe UI",10);StartPosition=FormStartPosition.CenterScreen;FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;
  TextLabel("F  /  FREEDOM GPT",35,28,480,32,13,accent);
  language=new ComboBox{Location=new Point(598,30),Size=new Size(123,28),DropDownStyle=ComboBoxStyle.DropDownList};language.Items.AddRange(new object[]{"Русский","English"});language.SelectedIndex=UseEnglish?1:0;
  language.SelectedIndexChanged+=(s,e)=>{string keep=folder.Text;bool keepOpen=open.Checked,keepShortcut=shortcut.Checked;UseEnglish=language.SelectedIndex==1;Build();folder.Text=keep;open.Checked=keepOpen;shortcut.Checked=keepShortcut;};Controls.Add(language);
  TextLabel(L("Ваш ИИ. На вашем ПК.","Your AI. On your PC."),35,88,680,53,28,Color.White);
  TextLabel(L("Чаты, код и изображения. Модели выбираете вы.","Chats, code, and images. You choose the models."),38,150,680,27,12,Color.FromArgb(164,164,176));
  TextLabel(L("КУДА УСТАНОВИТЬ","INSTALL LOCATION"),38,210,680,24,9,accent);
  folder=new TextBox{Location=new Point(38,242),Size=new Size(554,30),BackColor=panel,ForeColor=Color.White,BorderStyle=BorderStyle.FixedSingle};folder.Text=DefaultFolder();Controls.Add(folder);
  browse=new Button{Text=L("Выбрать…","Browse\u2026"),Location=new Point(606,240),Size=new Size(115,33),FlatStyle=FlatStyle.Flat};browse.Click+=(s,e)=>{using(var picker=new FolderBrowserDialog{Description=L("Выберите папку Freedom GPT на внутреннем или внешнем SSD","Select the Freedom GPT folder on an internal or external SSD"),SelectedPath=folder.Text})if(picker.ShowDialog()==DialogResult.OK)folder.Text=Path.Combine(picker.SelectedPath,"FreedomGPT");};Controls.Add(browse);
  TextLabel(L("Все модели, чаты и временные файлы будут внутри этой папки.\nМодели загружаются после проверки компьютера при первом запуске.","All models, chats, and temporary files will be stored in this folder.\nModels are downloaded after a PC check on first launch."),38,287,680,45,10,Color.FromArgb(164,164,176));
  open=new CheckBox{Text=L("Запустить после установки","Launch after installation"),Checked=true,Location=new Point(38,348),Size=new Size(330,25)};Controls.Add(open);
  shortcut=new CheckBox{Text=L("Создать ярлык на рабочем столе","Create desktop shortcut"),Checked=true,Location=new Point(38,376),Size=new Size(350,25)};Controls.Add(shortcut);
  progress=new ProgressBar{Location=new Point(38,419),Size=new Size(683,5),Style=ProgressBarStyle.Continuous};Controls.Add(progress);
  status=TextLabel(L("Бесплатно · Windows x64 · компоненты и лицензии включены","Free \u00b7 Windows x64 \u00b7 components and licenses included"),38,438,450,50,9,Color.FromArgb(164,164,176));
  install=new Button{Text=L("Установить Freedom GPT","Install Freedom GPT"),Location=new Point(492,447),Size=new Size(229,45),BackColor=accent,ForeColor=bg,FlatStyle=FlatStyle.Flat};Controls.Add(install);install.Click+=Install;
 }
 static string DefaultFolder(){if(Directory.Exists("A:\\"))return "A:\\CodexProjects\\FreedomGPT";foreach(var drive in DriveInfo.GetDrives())if(drive.IsReady&&drive.Name!="C:\\"&&(drive.DriveType==DriveType.Fixed||drive.DriveType==DriveType.Removable))return Path.Combine(drive.Name,"FreedomGPT");return "C:\\FreedomGPT";}
 async void Install(object sender,EventArgs ev){
  string destination=folder.Text;language.Enabled=false;install.Enabled=false;browse.Enabled=false;folder.Enabled=false;
  try {
   await Task.Run(()=>Extract(destination,(percent,name)=>BeginInvoke((Action)(()=>{progress.Value=percent;status.Text=name;}))));
   Directory.CreateDirectory(Path.Combine(destination,"data"));
   File.WriteAllText(Path.Combine(destination,"data","settings.json"),"{\"active\":null,\"model_port\":19135,\"ui_port\":19166,\"auto_update\":true,\"language\":\""+(UseEnglish?"en":"ru")+"\"}");
   string executable=Path.Combine(Path.GetFullPath(destination),"FreedomGPT.exe");
   if(shortcut.Checked){Type type=Type.GetTypeFromProgID("WScript.Shell");dynamic shell=Activator.CreateInstance(type);dynamic link=shell.CreateShortcut(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),"Freedom GPT.lnk"));link.TargetPath=executable;link.WorkingDirectory=Path.GetDirectoryName(executable);link.IconLocation=executable+",0";link.Save();}
   if(open.Checked)Process.Start(new ProcessStartInfo(executable){WorkingDirectory=destination,UseShellExecute=true});
   progress.Value=100;status.Text=L("Готово. При первом запуске приложение проверит ПК и предложит модели.","Done. On first launch, the app will check your PC and suggest models.");install.Text=L("Готово","Done");install.Enabled=true;install.Click-=Install;install.Click+=(s,e)=>Close();
  }catch(Exception error){MessageBox.Show(error.Message,L("Установка не завершена","Installation incomplete"),MessageBoxButtons.OK,MessageBoxIcon.Error);status.Text=L("Файлы сохранены. Для новой установки выберите пустую папку.","Files saved. For a new installation, select an empty folder.");install.Enabled=true;browse.Enabled=true;folder.Enabled=true;language.Enabled=true;}
 }
 static void Extract(string value,Action<int,string> update){
  string target=Path.GetFullPath(value).TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar;
  if(target.Length<4)throw new IOException(L("Выберите отдельную папку, например E:\\FreedomGPT.","Select a separate folder, e.g., E:\\FreedomGPT."));
  foreach(string special in new[]{Environment.GetFolderPath(Environment.SpecialFolder.Windows),Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles)})if(!String.IsNullOrEmpty(special)&&target.StartsWith(special+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new IOException(L("Выберите папку вне Windows, Program Files и профиля пользователя, например D:\\FreedomGPT.","Select a folder outside Windows, Program Files, and the user profile, e.g., D:\\FreedomGPT."));
  if(Directory.Exists(target)&&Directory.GetFileSystemEntries(target).Length>0)throw new IOException(L("Папка не пустая. Существующие файлы не заменяются. Выберите новую папку.","Folder is not empty. Existing files will not be replaced. Select a new folder."));
  using(var stream=File.OpenRead(Self)){
   if(stream.Length<64)throw new IOException(L("Повреждённый установщик.","Corrupted installer."));stream.Seek(-64,SeekOrigin.End);var reader=new BinaryReader(stream);string magic=Encoding.ASCII.GetString(reader.ReadBytes(16));long offset=reader.ReadInt64(),length=reader.ReadInt64();byte[] expected=reader.ReadBytes(32);
   if(magic!="FREEDOMGPTPKG001"||offset<0||length<1||offset+length!=stream.Length-64)throw new IOException(L("Архив установщика не найден.","Installer archive not found."));
   var slice=new SliceStream(stream,offset,length);update(0,L("Проверка целостности установщика…","Verifying installer integrity\u2026"));byte[] actual;using(var hash=SHA256.Create())actual=hash.ComputeHash(slice);for(int i=0;i<32;i++)if(actual[i]!=expected[i])throw new IOException(L("SHA256 установщика не совпал. Скачайте его заново.","Installer SHA256 mismatch. Please download it again."));
   slice.Position=0;using(var zip=new ZipArchive(slice,ZipArchiveMode.Read,true)){
    long total=0,done=0;foreach(var entry in zip.Entries)total+=entry.Length;
    var disk=new DriveInfo(Path.GetPathRoot(target));if(disk.AvailableFreeSpace<total+1073741824L)throw new IOException(L("Для установки недостаточно свободного места.","Not enough free space to install."));
    Directory.CreateDirectory(target);
    foreach(var entry in zip.Entries){string file=Path.GetFullPath(Path.Combine(target,entry.FullName));if(!file.StartsWith(target,StringComparison.OrdinalIgnoreCase))throw new IOException(L("Недопустимый путь в архиве.","Invalid path in archive."));if(entry.FullName.EndsWith("/")){Directory.CreateDirectory(file);continue;}Directory.CreateDirectory(Path.GetDirectoryName(file));using(var input=entry.Open())using(var output=new FileStream(file,FileMode.CreateNew,FileAccess.Write))input.CopyTo(output);done+=entry.Length;update((int)(done*100/Math.Max(1,total)),Path.GetFileName(file));}
   }
  }
 }
}
