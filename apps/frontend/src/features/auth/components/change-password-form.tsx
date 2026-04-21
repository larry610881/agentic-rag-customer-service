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
import { useChangePassword } from "@/hooks/queries/use-auth";
import { ROUTES } from "@/routes/paths";

const changePasswordSchema = z
  .object({
    old_password: z.string().min(1, "請輸入舊密碼"),
    new_password: z
      .string()
      .min(8, "新密碼至少 8 碼")
      .max(128, "新密碼最多 128 碼"),
    confirm_password: z.string().min(1, "請再次輸入新密碼"),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "兩次新密碼輸入不一致",
    path: ["confirm_password"],
  })
  .refine((data) => data.old_password !== data.new_password, {
    message: "新密碼不可與舊密碼相同",
    path: ["new_password"],
  });

type ChangePasswordFormValues = z.infer<typeof changePasswordSchema>;

function mapErrorMessage(error: unknown): string {
  const status = (error as { status?: number } | null)?.status;
  if (status === 400) return "舊密碼錯誤";
  if (status === 404) return "找不到使用者";
  if (status === 422) return "新密碼不可與舊密碼相同";
  if (status === 401) return "登入已過期，請重新登入";
  return "變更失敗，請稍後再試";
}

export function ChangePasswordForm() {
  const navigate = useNavigate();
  const mutation = useChangePassword();

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<ChangePasswordFormValues>({
    resolver: zodResolver(changePasswordSchema),
  });

  const onSubmit = (data: ChangePasswordFormValues) => {
    mutation.mutate(
      { old_password: data.old_password, new_password: data.new_password },
      {
        onSuccess: () => {
          reset();
        },
      },
    );
  };

  const isSuccess = mutation.isSuccess;
  const errorMessage = mutation.isError ? mapErrorMessage(mutation.error) : null;

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>變更密碼</CardTitle>
        <CardDescription>驗證舊密碼後輸入新密碼</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="old_password">舊密碼</Label>
            <Input
              id="old_password"
              type="password"
              autoComplete="current-password"
              placeholder="請輸入目前密碼"
              {...register("old_password")}
            />
            {errors.old_password && (
              <p className="text-sm text-destructive">
                {errors.old_password.message}
              </p>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="new_password">新密碼</Label>
            <Input
              id="new_password"
              type="password"
              autoComplete="new-password"
              placeholder="至少 8 碼"
              {...register("new_password")}
            />
            {errors.new_password && (
              <p className="text-sm text-destructive">
                {errors.new_password.message}
              </p>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="confirm_password">確認新密碼</Label>
            <Input
              id="confirm_password"
              type="password"
              autoComplete="new-password"
              placeholder="再次輸入新密碼"
              {...register("confirm_password")}
            />
            {errors.confirm_password && (
              <p className="text-sm text-destructive">
                {errors.confirm_password.message}
              </p>
            )}
          </div>

          {errorMessage && (
            <p className="text-sm text-destructive">{errorMessage}</p>
          )}

          {isSuccess && (
            <div
              className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200"
              role="status"
            >
              密碼已成功變更。下次登入請使用新密碼。
            </div>
          )}

          <div className="flex gap-2">
            <Button
              type="submit"
              disabled={mutation.isPending}
              className="flex-1"
            >
              {mutation.isPending ? "變更中..." : "變更密碼"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate(ROUTES.CHAT)}
            >
              返回
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
