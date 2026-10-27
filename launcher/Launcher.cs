using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class Launcher
{
    [STAThread]
    private static void Main()
    {
        string home = AppDomain.CurrentDomain.BaseDirectory;
        string python = Path.GetFullPath(Path.Combine(home, "..", ".venv", "Scripts", "pythonw.exe"));
        string entry = Path.Combine(home, "run.py");
        try
        {
            string desktop = Path.Combine(home, "ClashStudio.exe");
            if (File.Exists(desktop))
            {
                ProcessStartInfo native = new ProcessStartInfo(desktop);
                native.WorkingDirectory = home;
                native.UseShellExecute = false;
                Process.Start(native);
                return;
            }
            if (!File.Exists(python) || !File.Exists(entry) ||
                !File.Exists(Path.Combine(home, "frontend", "dist", "index.html")))
                throw new FileNotFoundException("Required local runtime or frontend build is missing. Keep this folder beside the original project's .venv folder.");
            ProcessStartInfo info = new ProcessStartInfo(python, "\"" + entry + "\"");
            info.WorkingDirectory = home;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            Process.Start(info);
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message, "Clash Studio 1.0", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
