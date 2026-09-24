using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;

internal static class Native
{
    [Flags]
    public enum ProcessAccess : uint
    {
        QueryInformation = 0x0400,
        VMRead = 0x0010
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern nint OpenProcess(
        ProcessAccess access,
        bool inheritHandle,
        int processId);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool CloseHandle(nint handle);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool ReadProcessMemory(
        nint process,
        nint address,
        byte[] buffer,
        nuint size,
        out nuint bytesRead);
}

internal static class Program
{
    private const string ProcessName = "DyingLightGame";

    private static void Main()
    {
        Console.OutputEncoding = Encoding.UTF8;
        Console.Title = "Dying Light Aim Tool v0.1";

        Console.WriteLine("==============================================");
        Console.WriteLine(" Dying Light Aim Tool v0.1");
        Console.WriteLine(" 独立外部工具 - 第一阶段诊断版");
        Console.WriteLine("==============================================");
        Console.WriteLine();
        Console.WriteLine("本版本不会修改游戏内存。");
        Console.WriteLine("只连接游戏进程并读取模块信息。");
        Console.WriteLine();

        Process? game = FindGame();

        if (game is null)
        {
            Console.WriteLine("未找到 DyingLightGame.exe");
            Console.WriteLine();
            Console.WriteLine("请启动《消逝的光芒》并进入实际游戏场景，");
            Console.WriteLine("然后重新运行本程序。");
            Console.WriteLine();
            Console.WriteLine("按任意键退出...");
            Console.ReadKey();
            return;
        }

        Console.WriteLine("已找到游戏进程");
        Console.WriteLine($"PID       : {game.Id}");
        Console.WriteLine($"进程名称  : {game.ProcessName}.exe");

        try
        {
            Console.WriteLine($"游戏路径  : {game.MainModule?.FileName}");
        }
        catch
        {
            Console.WriteLine("游戏路径  : 无法读取（权限不足）");
        }

        Console.WriteLine();
        Console.WriteLine("关键模块：");

        foreach (ProcessModule module in game.Modules)
        {
            string name = module.ModuleName ?? string.Empty;

            if (name.Equals("DyingLightGame.exe", StringComparison.OrdinalIgnoreCase) ||
                name.Equals("gamedll_x64_rwdi.dll", StringComparison.OrdinalIgnoreCase) ||
                name.Equals("engine_x64_rwdi.dll", StringComparison.OrdinalIgnoreCase) ||
                name.Equals("filesystem_x64_rwdi.dll", StringComparison.OrdinalIgnoreCase))
            {
                Console.WriteLine(
                    $"  {name,-30} Base=0x{module.BaseAddress.ToInt64():X16}  Size=0x{module.ModuleMemorySize:X}");
            }
        }

        nint handle = Native.OpenProcess(
            Native.ProcessAccess.QueryInformation | Native.ProcessAccess.VMRead,
            false,
            game.Id);

        if (handle == 0)
        {
            Console.WriteLine();
            Console.WriteLine($"OpenProcess 失败，Win32Error={Marshal.GetLastWin32Error()}");
            Console.WriteLine("可以尝试以管理员身份运行本工具。");
        }
        else
        {
            Console.WriteLine();
            Console.WriteLine("进程读取权限：OK");

            try
            {
                ProcessModule? main = game.MainModule;

                if (main != null)
                {
                    byte[] buffer = new byte[32];

                    bool ok = Native.ReadProcessMemory(
                        handle,
                        main.BaseAddress,
                        buffer,
                        (nuint)buffer.Length,
                        out nuint read);

                    Console.WriteLine($"读取主模块：{(ok ? "OK" : "失败")}");
                    Console.WriteLine($"读取字节数：{read}");

                    if (ok && read > 0)
                    {
                        Console.WriteLine("模块头部：");
                        Console.WriteLine(BitConverter.ToString(buffer, 0, (int)read));
                    }
                }
            }
            finally
            {
                Native.CloseHandle(handle);
            }
        }

        Console.WriteLine();
        Console.WriteLine("==============================================");
        Console.WriteLine("第一阶段测试完成。");
        Console.WriteLine("请把从“已找到游戏进程”开始的完整输出发回来。");
        Console.WriteLine("==============================================");
        Console.WriteLine();
        Console.WriteLine("按任意键退出...");
        Console.ReadKey();
    }

    private static Process? FindGame()
    {
        Process[] processes = Process.GetProcessesByName(ProcessName);

        foreach (Process process in processes)
        {
            try
            {
                _ = process.MainModule;
                return process;
            }
            catch
            {
                process.Dispose();
            }
        }

        return null;
    }
}
