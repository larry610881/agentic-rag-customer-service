import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useLogin } from "@/hooks/queries/use-auth";

const loginSchema = z.object({
  account: z.string().min(1, "請輸入帳號"),
  password: z.string().min(1, "請輸入密碼"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export function LoginForm() {
  const navigate = useNavigate();
  const loginMutation = useLogin();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = (data: LoginFormValues) => {
    loginMutation.mutate(data, {
      onSuccess: () => {
        navigate("/chat", { replace: true });
      },
    });
  };

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>登入</CardTitle>
        <CardDescription>登入您的帳號</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="account">帳號</Label>
            <Input
              id="account"
              type="text"
              placeholder="請輸入帳號"
              {...register("account")}
            />
            {errors.account && (
              <p className="text-sm text-destructive">{errors.account.message}</p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="password">密碼</Label>
            <Input
              id="password"
              type="password"
              placeholder="請輸入密碼"
              {...register("password")}
            />
            {errors.password && (
              <p className="text-sm text-destructive">{errors.password.message}</p>
            )}
          </div>
          {loginMutation.isError && (
            <p className="text-sm text-destructive">
              登入失敗，請確認帳號密碼是否正確。
            </p>
          )}
          <Button type="submit" disabled={loginMutation.isPending}>
            {loginMutation.isPending ? "登入中..." : "登入"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
